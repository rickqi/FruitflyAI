# Fly64 跨领域能力树 — 思维导图

> PlantUML `@startmindmap` 格式 — 展示从Fly64核心引擎到13大领域的完整能力分支

## 全局能力树

```plantuml
@startmindmap
top to bottom direction

*[#1a237e] Fly64 果蝇脑模型
**[#536dfe] L0: LIF脉冲推理引擎
***[#80deea] FlyModel 166K神经元 · 151.9M突触 · 50Hz确定性推理
***[#80deea] OU噪声 · 突触缓冲 · 滑动窗口投票
***[#80deea] 种子64确定性可复现 · 跨领域零修改

**_[#536dfe] L1: 输入编码与感知层
***[#80deea] SphericalRetina 270°复眼 · 1536采样点 · 16扇区光流
***[#80deea] ON/OFF/持续三通道 · 颜色5通道 · EMD评估
***[#80deea] 场景签名128维随机投影 · 小目标跟踪

**_[#536dfe] L2: 空间感知与导航层
***[#80deea] CentralComplex 16列环形吸引子 · 概率分布编码
***[#80deea] Memory 50×50网格 · 路径积分 · 拓扑聚类
***[#80deea] TurnAdaptation · 目标记忆衰减 · 航向偏差补偿

**_[#536dfe] L3: 联想学习与动作选择层
***[#80deea] MushroomBody 2000KC→5MBON · 5%稀疏编码
***[#80deea] 三因子Hebbian ΔW=η·R(t)·E_p·target
***[#80deea] 多巴胺增益5通路 · 记忆巩固 · 资格痕迹5帧窗口

**_[#536dfe] L4: 反射与异常检测层
***[#80deea] ReflexController 4类反射 · 快慢双轨 · 滞环
***[#80deea] MotionStateDetector 6状态 · 3σ统计异常
***[#80deea] 200事件环形缓冲 · 因果链时间线

**_[#536dfe] L5: 元认知与自进化层
***[#80deea] 5阶段EVO闭环: Monitor→Diagnose→Fix→Verify→Document
***[#80deea] LLM教官(GLMConsultant) · StrategyWriter · 热加载
***[#80deea] 仪表板70+指标 · trajectory.json · evolution_history

left side

+[#00bfa5] ★ 原始7大迁移领域
++[#a5d6a7] 工业质检 (S级·80%复用·6周)
+++ ON/OFF+EMD直接复用 · 色彩校准CALIBRATION v2
+++ 16扇区→8异常分类 · 小目标跟踪
+++ 里程碑: 检测准确率>95% · 误报率<2%
++[#a5d6a7] 机器人导航&SLAM (S级·70%复用·10周)
+++ CX环形吸引子=SLAM前端(数学等价) · mmap协议扩展
+++ 路径积分+场景匹配回环检测
+++ 里程碑: 导航成功率>90% · 回环精度>95%
++[#a5d6a7] 保险核保 (A级·60%复用·12周)
+++ 16风险因子概率分布 · 多巴胺5通路=5核保政策因子
+++ 里程碑: 自动核保率>75% · 综合准确率>90%
++[#a5d6a7] 多Agent自治系统 (A级·55%复用·8周)
+++ STMD最小通信架构 · 分布式EVO闭环
+++ 里程碑: 10Agent心跳同步>99% · 故障恢复<10s
++[#a5d6a7] 自动驾驶 (A级·65%复用·12周)
+++ τ估计↔AEB数学等价 · 因果链→事故责任认定
+++ 里程碑: AEB误差<0.1s · 行人召回>90%
++[#a5d6a7] 量化交易 (B级·50%复用·16周)
+++ MarketFeatureEncoder · 多巴胺→PnL奖励映射
+++ 里程碑: 夏普>1.0 · 最大回撤<15%
++[#a5d6a7] 机械臂操控 (B级·45%复用·12周)
+++ MBON→IK集成 · 状态编码器 · 多巴胺奖励函数
+++ 里程碑: 静态抓取>80% · 5物体泛化>70%

--[#ff6d00] ★ 新增6大高潜力领域
--[#ffe082] 游戏AI (P0·★★★★★·1-2月·已验证Steam)
--- 连接组NPC(166K涌现行为) · DDA自适应难度 · PCG程序化生成
--- FlyMuse 2026已上线商业游戏 · 多游戏验证(Doom/SM64/HL/MC)
--- 商业路径: NPC-as-a-Service · DDA中间件 · 测试自动化
--[#ffe082] 医疗诊断 (P0·★★★★★·3-6月)
--- 嗅觉回路→生物标志物检测 · KC-MBON→疾病分类
--- ICU多模态监控(6状态·快慢双轨) · CX→患者状态概率
--- EEG-SNN达98.3%(JEA 2025) · 数据漂移自愈(EVO闭环)
--[#ffe082] 能源调度 (P1·★★★★☆·4-8月)
--- CX负荷概率分布 · LIF→可再生能源预测 · 反射→电网故障
--- 分布式EVO→微电网自治(每节点独立Agent)
--- 学术支持: AIMS 2026 · 中科院2025负荷预测
--[#ffe082] 环境监测 (P1·★★★★·2-3月)
--- 蘑菇体→污染物检测 · 异常检测→超标预警
--- 50×50空间网格→污染源定位 · EVENT缓冲→审计追踪
--[#ffe082] 农业智能 (P1·★★★★·3-4月)
--- 270°复眼→多光谱无人机巡检 · 16扇区→作物分类
--- UV近似→NDVI替代 · 50×50网格→精耕区管理
--[#ffe082] 药物发现 (P2·★★★★★·6-12月)
--- 128维签名→分子指纹哈希 · KC-MBON→活性预测
--- 三因子Hebbian→先导优化 · 资格痕迹→动力学轨迹
--- ACS验证: SNN发现新冠先导化合物

@endmindmap
```

---

## 能力-领域热力分支图 (核心能力 × 领域映射)

```plantuml
@startmindmap
*[#1a237e] Fly64核心能力 → 领域适配热度
right to left direction

right side
**_[#536dfe] LIF SNN推理引擎
***[#a5d6a7] ★★★★★ 保险核保 / 量化交易 / 机械臂 / 游戏AI / 医疗诊断 / 药物发现
***[#a5d6a7] ★★★★ 工业质检 / 机器人导航 / 能源调度
***[#ffe082] ★★★ 农业智能
***[#ffcdd2] ★★ 环境监测

**_[#536dfe] CX环形吸引子/导航
***[#a5d6a7] ★★★★★ 机器人导航 / 能源调度 / 自动驾驶 / 农业智能
***[#a5d6a7] ★★★★ 医疗诊断(分期) / 环境监测
***[#ffe082] ★★★ 游戏AI(PCG) / 保险核保
***[#ffcdd2] ★★ 机械臂操控

**_[#536dfe] 蘑菇体学习(联想)
***[#a5d6a7] ★★★★★ 保险核保 / 游戏AI / 医疗诊断 / 药物发现 / 量化交易
***[#a5d6a7] ★★★★ 能源调度 / 环境监测 / 机械臂
***[#ffe082] ★★★ 工业质检 / 农业智能 / 自动驾驶
***[#ffcdd2] ★★ 多Agent系统

**_[#536dfe] 异常检测(快慢双轨)
***[#a5d6a7] ★★★★★ 医疗诊断(ICU) / 工业质检 / 自动驾驶 / 能源调度
***[#a5d6a7] ★★★★ 环境监测 / 多Agent / 保险核保
***[#ffe082] ★★★ 机械臂 / 游戏AI / 农业智能
***[#ffcdd2] ★★ 量化交易

**_[#536dfe] 自我进化闭环(EVO)
***[#a5d6a7] ★★★★★ 全部13领域 · 通用自治范式
***[#80deea] >> Monitor→Diagnose→Fix→Verify→Document 通用5步 <<
***[#80deea] >> 跨领域零修改 — 仅需替换诊断指标 <<

left side
--[#00bfa5] ★ 代码复用度排行
--[#a5d6a7] 80% 工业质检 (零修改: ON/OFF/EMD/Reflex/EVO)
--[#a5d6a7] 70% 机器人导航 (零修改: CX/Memory/Reflex/EMD)
--[#a5d6a7] 65% 自动驾驶 (零修改: τ估计/悬崖检测/因果链/EMD)
--[#a5d6a7] 60% 保险核保 (零修改: LIF/Reflex/EVO/LLM)
--[#a5d6a7] 55% 多Agent系统 (零修改: PluginRunner/EVO/HealthChecker)
--[#ffe082] 50% 量化交易 (零修改: LIF/MushroomBody/OU/EVO)
--[#ffcdd2] 45% 机械臂操控 (零修改: MushroomBody/Hebbian/Reflex)

--[#ff6d00] ★ 实施推荐顺序
--[#a5d6a7] Phase 1 (第1-2月): 工业质检 + 机器人导航
--[#a5d6a7] Phase 2 (第3-5月): 保险核保 + 多Agent系统
--[#ffe082] Phase 3 (第6-8月): 游戏AI + 医疗诊断 + 自动驾驶
--[#ffe082] Phase 4 (第9-12月): 量化交易 + 能源调度 + 机械臂
--[#ffcdd2] Phase 5 (第12-18月): 药物发现 + 环境监测 + 农业智能

@endmindmap
```

---

## 六层架构引擎详图

```plantuml
@startmindmap
*[#1a237e] Fly64 六层神经形态引擎架构
top to bottom direction

**_[#536dfe] L5: 元认知层
***[#80deea] evolution_skill.py · Monitor(全链路70+指标)
***[#80deea] Diagnose(根因分析) · Fix(active_strategy热加载)
***[#80deea] GLMConsultant(LLM教官) · StrategyWriter(策略生成)
***[#80deea] Verify(A/B测试) · Document(evolution_history.json)

**_[#536dfe] L4: 反射与异常检测层
***[#80deea] ReflexController: stuck/fallen/cliff/flow_anomaly/scene_change
***[#80deea] MotionStateDetector: 6状态×三路投票×3σ异常
***[#80deea] 快慢双轨: 快路径<50ms硬编码 · 慢路径LLM推理
***[#80deea] 200事件环形缓冲 · 因果链时间线

**_[#536dfe] L3: 联想学习与动作选择层
***[#80deea] MushroomBody: 2000KC 5%稀疏编码 → 5MBON
***[#80deea] 三因子Hebbian: ΔW = η · R(t) · E_p · target
***[#80deea] 多巴胺5通路增益: visual/forward/turn/jump/recurrent
***[#80deea] 资格痕迹5帧 · 记忆巩固阈值0.6 · 最大10条

**_[#536dfe] L2: 空间感知与导航层
***[#80deea] CentralComplex: 16列环形吸引子 · 22.5°/列
***[#80deea] COMPASS_PERSISTENCE=0.85 · MAX_STEERING=0.15
***[#80deea] 局部兴奋1.2 + 全局抑制0.25
***[#80deea] Memory: 50×50网格 · 路径积分 · 场景签名128维

**_[#536dfe] L1: 输入编码与感知层
***[#80deea] SphericalRetina: 270°×144° · 1536采样点
***[#80deea] 16扇区光流→8地形分类 · ON/OFF/持续三通道
***[#80deea] 颜色5通道(R/G/B/UV_approx/HSV) · EMD运动边界
***[#80deea] 小目标跟踪: 连通分量+卡尔曼滤波

**_[#536dfe] L0: LIF脉冲推理引擎
***[#80deea] FlyModel: 166K神经元 · 151.9M突触 · 50Hz
***[#80deea] model.npz + weights.npz + brain_connection.pkl
***[#80deea] OU噪声 θ=2.0/σ=0.10 · 突触缓冲衰减0.65
***[#80deea] 滑动窗口13帧投票 · 种子64确定性

@endmindmap
```

---

*思维导图由 AgentTeams brain-model-deep-expansion domain-architect 生成*  
*渲染方式: 将每个 ```plantuml 块复制到 PlantUML 在线渲染器或本地 PlantUML 环境*