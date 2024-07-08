# 主要流程

"""
0  wfInit
1  wfJoin
2  wfConfig
3  wfStart -> 4
4  wfSendRole -> 5
5  wfGoNight -> 6
6  wfSendSkill
7  wfSkillProc -> 6 / 8
8  wfSendDeath (11) -> 9
9  wfDiscuss -> 9 / 10
10 wfVote (11)
11 wfCheckOver -> 12
12 wfEnd
"""


roleAlias: dict[str, int] = {
    "0": 0,
    "平民": 0,
    "好人": 0,
    "1": 1,
    "狼": 1,
    "狼人": 1,
    "2": 2,
    "预": 2,
    "预言": 2,
    "预言家": 2,
    "3": 3,
    "女巫": 3,
    "4": 4,
    "守": 4,
    "守卫": 4,
    "5": 5,
    "骑": 5,
    "骑士": 5,
    "6": 6,
    "猎": 6,
    "猎人": 6,
    "7": 7,
    "王": 7,
    "狼王": 7,
    "8": 8,
    "白狼": 8,
    "白狼王": 8,
    "9": 9,
    "隐": 9,
    "隐狼": 9,
    "10": 10,
    "白痴": 10,
    "傻瓜": 10,
}
