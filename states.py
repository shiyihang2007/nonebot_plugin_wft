# 维护流程信息

from .units import RoleBase

# 参与的用户
ActiveUsers: list[str] = []
# 使用的群
ActiveGroup: str = ""

# 角色配置
RoleCnt: list[int] = []
# [人,狼,神]
RoleConfig: dict[int, int] = {}

# 身份映射
UserId2Role: dict[str, RoleBase] = {}
Num2UserId: dict[int, str] = {}

# 游戏状态
NowState: int = 0
"""
- `0` - 准备阶段
- `1` - 初始化阶段
- `2` - 夜晚阶段
- `3` - 白天阶段
- `4` - 结算阶段
"""

# 死亡人数
DeathList: list[int] = []
