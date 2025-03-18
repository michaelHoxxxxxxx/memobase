import asyncio
from collections import defaultdict
from .types import MergeAddResult, PROMPTS, AddProfile
from ....prompts.types import get_specific_subtopics, attribute_unify
from ....prompts.utils import parse_string_into_subtopics
from ....models.utils import Promise
from ....models.response import ProfileData
from ....env import CONFIG, LOG, ProfileConfig, ContanstTable
from ....llms import llm_complete


async def organize_profiles(
    project_id: str,
    profile_options: MergeAddResult,
    config: ProfileConfig,
) -> Promise[None]:
    profiles = profile_options["before_profiles"]
    use_language = config.language or CONFIG.language
    topic_groups = defaultdict(list)
    for p in profiles:
        topic_groups[p.attributes[ContanstTable.topic]].append(p)

    need_to_organize_topics: dict[str, list[ProfileData]] = {}
    for topic, group in topic_groups.items():
        if len(group) > CONFIG.max_profile_subtopics:
            need_to_organize_topics[topic] = group

    if not len(need_to_organize_topics):
        return Promise.resolve(None)
    ps = await asyncio.gather(
        *[
            organize_profiles_by_topic(project_id, group, use_language)
            for group in need_to_organize_topics.values()
        ]
    )
    if not all([p.ok() for p in ps]):
        errmsg = "\n".join([p.msg() for p in ps if not p.ok()])
        return Promise.reject(f"Failed to organize profiles: {errmsg}")

    delete_profile_ids = []
    for gs in need_to_organize_topics.values():
        delete_profile_ids.extend([p.id for p in gs])
    new_profiles = []
    for p in ps:
        new_profiles.extend(p.data())

    profile_options["add"].extend(new_profiles)
    profile_options["add"] = deduplicate_profiles(profile_options["add"])
    profile_options["delete"].extend(delete_profile_ids)
    return Promise.resolve(None)


async def organize_profiles_by_topic(
    project_id: str,
    profiles: list[ProfileData],
    use_language: str,  # profiles in the same topics
) -> Promise[list[AddProfile]]:
    assert (
        len(profiles) > CONFIG.max_profile_subtopics
    ), f"Unknown Error,{len(profiles)} is not greater than max_profile_subtopics: {CONFIG.max_profile_subtopics}"
    assert all(
        p.attributes[ContanstTable.topic] == profiles[0].attributes[ContanstTable.topic]
        for p in profiles
    ), f"Unknown Error, all profiles are not in the same topic: {profiles[0].attributes['topic']}"
    LOG.info(
        f"Organizing profiles for topic: {profiles[0].attributes['topic']} with sub_topics {len(profiles)}"
    )
    topic = attribute_unify(profiles[0].attributes[ContanstTable.topic])
    suggest_subtopics = get_specific_subtopics(
        topic, PROMPTS[use_language]["profile"].CANDIDATE_PROFILE_TOPICS
    )

    llm_inputs = "\n".join(
        [
            f"- {p.attributes['sub_topic']}{CONFIG.llm_tab_separator}{p.content}"
            for p in profiles
        ]
    )
    llm_prompt = f"""topic: {topic}
{llm_inputs}
"""
    p = await llm_complete(
        project_id,
        llm_prompt,
        PROMPTS[use_language]["organize"].get_prompt(
            CONFIG.max_profile_subtopics // 2 + 1, suggest_subtopics
        ),
        temperature=0.2,  # precise
        **PROMPTS[use_language]["organize"].get_kwargs(),
    )
    if not p.ok():
        return p
    results = p.data()
    subtopics = parse_string_into_subtopics(results)
    reorganized_profiles: list[AddProfile] = [
        {
            "content": sp["memo"],
            "attributes": {
                ContanstTable.topic: topic,
                ContanstTable.sub_topic: sp[ContanstTable.sub_topic],
            },
        }
        for sp in subtopics
    ]
    if len(reorganized_profiles) == 0:
        return Promise.reject(
            "Failed to organize profiles, left profiles is 0 so maybe it's the LLM error"
        )
    # forcing the number of subtopics to be less than max_profile_subtopics // 2 + 1
    reorganized_profiles = reorganized_profiles[: CONFIG.max_profile_subtopics // 2 + 1]
    return Promise.resolve(reorganized_profiles)


def deduplicate_profiles(profiles: list[AddProfile]) -> list[AddProfile]:
    topic_subtopic = {}
    for nf in profiles:
        key = (
            nf["attributes"][ContanstTable.topic],
            nf["attributes"][ContanstTable.sub_topic],
        )
        if key in topic_subtopic:
            topic_subtopic[key]["content"] += f"; {nf['content']}"
            continue
        topic_subtopic[key] = nf
    return list(topic_subtopic.values())


if __name__ == "__main__":

    async def test_organize(topic, suggest_subtopics, llm_inputs, max_topics=8):
        llm_prompt = f"""topic: {topic}
    {llm_inputs}
    """
        p = await llm_complete(
            "__root__",
            llm_prompt,
            PROMPTS["zh"]["organize"].get_prompt(max_topics, suggest_subtopics),
            temperature=0.2,  # precise
            **PROMPTS["zh"]["organize"].get_kwargs(),
        )
        if not p.ok():
            return p
        results = p.data()
        print(results)

    llm_inputs = """
- 用餐习惯: 用户习惯用左手吃饭，食量不大、进食慢，嘴巴易鼓，不爱吃饭，喜欢糖果、零食，天天吃泡面，拒绝其他用餐方式，吃零食多影响正常吃饭，且用餐时喜欢玩手机
- 照顾他人习惯: 用户有照顾他人的习惯，曾在他人喝醉后照顾，如照顾徐平安，还在2025年2月13日10:23AM给小佳琪喂吃的。以前逛完街会要徐平安抱，现在不需要
- 消费习惯: 用户在与徐平安约会时有自己买单的意愿，且愿意为恋爱对象购买贵重礼物
- 抽烟习惯（此处可能表述不准确，应为吃槟榔习惯）: 用户有吃槟榔的习惯，和徐平安一起吃了和成天下槟榔
- 抽烟习惯（吃槟榔习惯）: 用户平时和徐平安一起吃槟榔，2025/02/07拒绝吃槟榔
- 抽烟习惯: 用户有抽烟习惯且较难戒掉，徐平安多次劝其戒烟，2025/02/13制止其抽烟并提醒少抽，用户认同，此外，用户不喜欢二手烟味。
- 手部动作习惯: 用户习惯把手放进口袋、主动或牵对方手，他人靠近或牵手时会退后。对话中会收回手、摇头、松开手，睡觉时手冷放他人肚子。还有摸脸、亲对方、手搭腰等习惯。
- 喝水习惯: 用户之前不太爱喝水，觉得水不好喝，更爱饮料，不喜欢苦水，需哄着喝。一开始拒绝喝水，经劝说喝了一口，现听从建议喝水，直播时、结束后及吃糖果和水果后会喝，但喝水量较少。
- 吃槟榔习惯: 用户有吃槟榔的行为，2025/02/09 04:20AM嚼槟榔致腮帮子累，2月13日吃了徐平安给的和成天下槟榔，徐平安制止后用户表示徐平安不买就不吃
- 保养习惯: 2025/02/07用户用冰块敷脸、敷面膜和眼膜保养，脸被辣椒和芥末刺激后也敷了面膜；使用脏脏脸特效，佩戴美瞳时划片。医生建议伤口别碰水，饮食清淡，少吃辣和酸豆角
- 休息地点: 用户习惯和小佳琪去菜铺、零食很忙等地活动，直播时会靠在他人或伴侣怀里睡着，喜欢睡在徐平安旁。结束后会在沙发、充气床等地休息，2025/02/12在酒店和小佳琪、徐平安一起，2月13日独自在床边睡。
- 休息习惯: 用户睡觉不老实，不要枕头且贪睡，需徐平安哄睡，习惯晚睡晚起、熬夜玩iPad。2025/02/16凌晨入睡，中午醒来，醒来发现徐平安不在会闹情绪。以前赖床要抱抱，现在睡醒自己洗漱
- 个人卫生习惯: 用户在2025/02/11去洗澡、刷牙、洗脸
"""
    import asyncio

    asyncio.run(test_organize("习惯", "None", llm_inputs, max_topics=4))
