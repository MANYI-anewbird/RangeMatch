# RangeMatch Agent 完整建设步骤清单

> 文档状态：Canonical（项目基准文档）
> 最后更新：2026-08-08
> 产品数据范围：United States（Mireye 当前覆盖）
> Initial validation scope：Selected U.S. regions and reference cases
> Operation Profiles：Cow-Calf Operation、Sheep Grazing

> 当前执行主线：只建设比赛所需的最小闭环，不以完成全部 Phase 为 Demo 前置条件。完整 Phase 清单是长期建设地图，而不是必须串行完成的发布计划。

## 0. 当前产品与工作流（项目负责人首页）

### 0.1 最终产品定义

> **RangeMatch 是一个受约束的农业土地尽调与匹配 Agent：Mireye 快速读取物理世界，专业开放数据补全 parcel facts，固定农业知识和确定性引擎完成牛羊匹配，LLM 负责理解用户、规划调查、调用工具、检查动态法规，并向买家解释下一步行动。**

当前比赛原型每次只评估一个美国 parcel，不提供 batch search、portfolio ranking、regional site discovery 或 Mireye ICP Finder。

### 0.2 用户模式

#### Goal-directed

用户指定当前支持的目标经营方式，例如 Cow-Calf。Planner 优先调查和展示用户选定的 Profile，但 Sheep 仍可作为 peer Profile 运行。用户意图只改变调查与展示顺序，不改变科学规则、数据标准或 Engine 判定。

#### Discovery

用户不指定经营方式。系统对 Cow-Calf 和 Sheep 进行平级评估，并必须说明结论仅限于当前支持的 Profiles；不得声称发现土地的客观最佳用途。

### 0.3 当前完整 Agent 工作流

```text
1. 用户通过地址或地图坐标定位土地，并显式确认 exactly one parcel polygon
2. LLM Intent Parser 将自然语言转成结构化意图
3. 解析并绑定 exactly one parcel，生成 geometry_hash
4. Deterministic Planner 生成受控调查 DAG
5. Mireye Property / Land / Hazards 提供 point/diligence context
6. Planner Executor 运行批准的 F01–F08 数据路径
7. 组装 Normalized Land Profile
8. Deterministic Engine 运行 Cow-Calf / Sheep Profiles
9. 生成 Unified Output + 完整参数/证据表
10. Public Diligence Agent 检索当前官方政策与尽调信息并保留引用
11. LLM Buyer Report Generator 生成人类可读报告
12. Deterministic Report Validator 核查数字、标签、引用和 unknowns
13. Dashboard + Readable Report + Evidence Appendix 展示结果
```

当前 Factor 执行是依赖 DAG，不是按编号串行：

```text
Resolve / validate geometry
├── Mireye Property / Land / Hazards contexts
└── F06 geometry gate
    ├── F01 Topography
    ├── F02 Herbaceous Resource ──→ F08 reuse same RAP coverV3
    ├── F03 Livestock Water
    ├── F04 Soil / Wetness / Ecological Site
    ├── F05 Climate / Drought
    └── F07 Road / Physical Access
```

报告和知识顺序始终保持 `F01 → F08`，不受执行完成顺序影响。

### 0.4 Mireye 与 F01–F08 的分工

```text
Mireye
→ parcel/jurisdiction 线索、point-level land context、hazard triggers、
  provenance 与 partial failures

F01–F08
→ parcel-wide、版本化、可复现的农业土地调查合同

Matching Engine
→ Factor signals、Operation labels、unknowns、constraints 与 diligence
```

Mireye point context 可被 F01/F02/F03/F04/F05/F08 引用作为 QA、快速背景或候选发现，但不得未经批准提升为 parcel-canonical Land Fact。F06 来自 geometry；F07 v0.1 来自 TIGER/Line。

Mireye live parcel lookup 与 Property/Land/Hazard context 已在干净网络完成验证。历史 SafeBrowse/TLS 拦截仍保留为 incident record；未来任何外部失败仍必须可见、fail closed，且不得静默替换为 fixture。

### 0.5 LLM 权限边界

```yaml
llm_can:
  - parse_user_intent
  - explain_unified_output
  - generate_buyer_readable_report
  - investigate_current_official_regulations
  - propose_reviewed_diligence_actions

llm_cannot:
  - invent_or_modify_land_facts
  - create_factor_signals
  - create_cow_sheep_ranking
  - change_engine_decision_labels
  - invent_thresholds_or_scores
  - promote_unknown_to_known
  - give_final_legal_conclusions
  - override_the_matching_engine
```

当前 Planner、Executor、Matching Engine 和 Unified Output 均为确定性实现。LLM 已用于受约束的 Intent Parsing 与 Buyer Report；Public Diligence Agent 可检索当前官方来源。两者都不进入 Match 裁决。

### 0.6 最终交付的两类报告

#### Buyer-Readable Report

由 LLM 根据 Unified Output 生成，并经 Validator 审核。当前买家报告按“结论 → parcel-specific facts → Cow/Sheep evidence comparison → top diligence actions → current official guidance → methodology”组织；不把系统字段或重复免责声明当作主要内容。

#### Evidence & Parameter Appendix

由程序确定性生成，保存 F01–F08 的全部参数、单位、source、coverage、applicability、provenance、limitations、unknowns、规则和版本。LLM 报告中的数字和事实引用必须能反向定位到该附录。

### 0.7 当前完成状态

```yaml
completed:
  factor_scope: F01_TO_F08_CLOSED
  matching_engine: true
  unified_output_contract: true
  executable_schema_and_projection: true
  planner_dependency_dag: true
  planner_executor: true
  mireye_live_parcel_and_context_paths: true
  one_parcel_api: true
  constrained_llm_intent_and_buyer_report: true
  deterministic_report_validator: true
  public_diligence_search_agent: true
  buyer_facing_dashboard_report_appendix: true
  backend_test_suite: 423_PASSED
  frontend_test_suite: 22_PASSED

deferred:
  - batch_search
  - portfolio_ranking
  - mireye_icp_finder
  - f09_plus
  - batch_and_portfolio_workflows
```

### 0.8 当前下一步

```text
Competition packaging and deployment readiness
→ end-to-end real-parcel rehearsal
→ demo reliability and failure-state QA
→ Docker / Agent Skill / submission package
```

### 0.9 文档阅读规则

- 本节是当前产品、进度和下一步的权威首页。
- `MVP_SPEC.md`、`PRODUCT_PROTOTYPE_SCOPE.md`、`AGENT_ORCHESTRATION_SPEC.md` 和 `F01_F08_UNIFIED_OUTPUT_CONTRACT.md` 是对应英文正式合同。
- 下方 Phase 清单是长期建设地图，未勾选项不代表比赛原型当前缺陷。
- 下方科学审核记录保留历史审计价值；若与本节状态冲突，以本节及对应英文 freeze/contract 文档为准，并应修正过期 checklist。

### 文档语言与提交规范

- 本步骤清单是唯一保留中文的 canonical 项目文档，供项目负责人查看和推进。
- 所有提交给 Mireye 或用于科学、工程审核的正式文件统一使用英文。
- `SOURCE_REGISTRY.md`、`SPECIES_REQUIREMENTS_REGISTRY.md`、`UNIFIED_LAND_VARIABLE_REGISTRY.yaml` 与 `DATA_SOURCE_AND_MIREYE_AUDIT.yaml` 是科学规格冻结前必须完成的四个正式英文文件。
- 每个 Operation Profile 必须能够从 requirement 反向追溯到 source URL/DOI、所需 Land Variable、Mireye 字段或外部数据来源，以及确定性信号规则。
- 中文研究报告只能作为 backup，不得成为 runtime knowledge、正式证据或 Mireye submission source。

### 地名与文字描述的数据化原则

> 系统判断的是可测量条件，不是地名。Texas、南方、北方、干旱地区、崎岖土地等文字描述，必须尽可能拆成具有单位、空间尺度、时间窗口、来源和不确定性的 Land Variables / Context Variables。

- [x] 建立英文 `CONTEXT_DECOMPOSITION_STANDARD.md` 作为 canonical governance。
- 地名、州名和 region name 只用于数据检索、jurisdiction、provenance、validation stratification 和人类可读解释，默认不得直接获得 suitability 权重。
- 经纬度和 parcel geometry 主要是空间索引；真正进入匹配的是根据位置取得的 elevation、climate、soil、vegetation、water、hazards、access 和 market context 等数据。
- 对“南方/北方”应拆成 temperature、humidity、heat days、freeze days、snow、growing season、precipitation seasonality 等实际变量。
- 对“干旱”应拆成 precipitation、evapotranspiration、aridity index、drought frequency/severity 和 soil-water capacity。
- 对“靠近人口/市场”应拆成指定 travel-time 范围内人口、道路时间、劳动力/服务可达性和市场距离；不得混入 biological suitability。
- 优先保存原始连续数值和 uncertainty，再由已审核的确定性方法生成 bins、index 或信号。
- 不是所有内容都必须强行数字化。soil class、ecological site、legal access、water-right status 等可保留受控分类，但不得把分类代码当成连续数值。
- 缺失值继续保持 `UNKNOWN`，不得为了快速判断而填零、平均值或默认地区特征。
- 跨州一致性测试：若两个不同州 parcel 的已审核输入变量相同，规则应给出相同解释；否则必须指出额外变量、法律差异或有证据的 regional modifier。

### 当前科学审核状态

- [x] F01 Cow-Calf 地形关系完成窄结论审核；数值规则未批准。
- [x] F01 Sheep 地形关系完成窄结论审核；通用坡度阈值未批准。
- [x] Goat Profile 已从 MVP active scope 删除；既有研究移入 archive，不参与运行或 Mireye submission。
- [x] 建立 F01 牛羊确定性 qualitative rule specification；当前 F01 不参与牛羊排名。
- [x] 建立 F01 golden tests，覆盖完整 parcel、point-only、missing、conflicting 和 provenance incomplete。
- [x] 冻结 F01 v0.1 parcel derivation 的 slope、elevation 和 aspect 方法及 provenance contract。
- [x] 建立 F01 derivation tests；ruggedness 与 topographic position 因尺度敏感继续保持 `METHOD_REVIEW_REQUIRED`。
- [x] 完成 F02 Herbaceous Resource 第一轮 atomicity decision 与 Cow-Calf/Sheep source-by-source audit。
- [x] 明确 `cover != production != available forage != palatable/nutritionally adequate forage`。
- [x] 完成 F02 RAP v3 文档级字段、版本、单位、时间语义和 API schema audit。
- [x] 实时验证 Mireye v0.14.0 catalog（304 fields）、OpenAPI、health/ready 与 `/v1/fetch` point contract。
- [x] 在 CPER 工程测试点取得 F01 elevation/slope/aspect，并确认这些只能用于 point QA，不能代替 parcel aggregation。
- [x] 审核 Mireye v0.14.0 F02 候选：仅发现 `lcms_class`/`cdl_class` 分类上下文，未发现可替代 RAP 的 numeric herbaceous cover/production fields。
- [x] RAP v3 live gate：`coverV3`、`productionV3`、`production16dayV3` polygon contract 全部通过；16-day 返回 23 个区间且合计与 annual production 在浮点容差内一致。
- [x] 建立 F02 v0.1 derivation spec：最近 10 个完整对齐年份、至少 8 年、relative IQR、23期原序列、annual consistency check，以及不使用通用季节标签。
- [x] 冻结 F02 mask/no-data 原则，并识别 RAP aggregate API 不返回 pixel-area coverage，因此成功响应仍为 `COVERAGE_UNQUANTIFIED`。
- [x] 建立 F02 v0.1 data-quality deterministic rules 与 golden tests；因 species requirements 尚待 final review，不输出方向性 resource signal 或排名。
- [x] 完成 improved-pasture applicability 审核：RAP 只批准用于已确认符合 rangeland domain 的分析范围；improved pasture/cultivated forage 默认 `OUTSIDE_DOCUMENTED_PRODUCT_SCOPE`。
- [x] 实测 CPER masked/unmasked aggregate 均返回数据且数值不同，但 API 不返回被 mask 的面积，禁止用数值差反推 coverage。
- [ ] 配置 authenticated GEE 或等价 version-matched raster access，计算 eligible、masked、no-data 和 valid area；此前保持 `COVERAGE_UNQUANTIFIED`。
- [x] 建立统一 `LAND_FACT_SCHEMA.yaml`，强制保存 observation、source、applicability、coverage、quality、provenance 和 limitations。
- [x] 冻结 Matching Engine gate 顺序：Applicability → Coverage → Provenance/Quality → Derivation → Scientific Relationship → Operation Comparison。
- [x] 将 RAP aggregate API 定义为 MVP fast path；`COVERAGE_UNQUANTIFIED` 只允许有限上下文并限制 confidence。
- [x] 将 RAP raster/GEE adapter 移入 optional enhancement path，不作为 MVP 硬依赖。
- [x] 建立 Land Fact gate golden tests，禁止“API 有值即适用”和“raster 成功即完整覆盖”。
- [x] 建立首个可执行 CPER Land Profile fixture，包含 F01/F02 facts、applicability、coverage、quality、provenance、limitations 与 unknowns。
- [x] 实现无第三方依赖的纯 Python Land Fact Gate 和 F01/F02 deterministic evaluator。
- [x] 生成首个结构化 MatchResult：牛羊均为 `HOLD`，F01=`CONTEXT_DEPENDENT`，F02=`NEEDS_VERIFICATION`，不允许 cross-profile ranking。
- [x] 建立并通过 10 项可执行测试，包括 identical-input determinism、missing preservation、applicability/coverage gate 和 LLM override prohibition。
- [x] 建立英文 `MIREYE_API_HANDOFF.md`、安全的 `.env.example` 和 `.gitignore`。
- [x] Mireye base URL 与 key 已通过本地 `.env` 提供；真实 key 未写入文档或 fixtures。
- [x] 选择 USDA-ARS CPER 作为首个 F01/F02 engineering validation site。
- [x] 创建约 140.7 ha 的 `ENGINEERING_TEST_GEOMETRY_CPER_001`，并明确它不是官方 pasture 或待售 parcel。
- [x] 保存 CPER public metadata coverage extent，作为 Test B stress/coverage geometry。
- [x] CPER Test A data access：Mireye point、锁定 source item 的 USGS 3DEP parcel derivation、RAP cover/annual/16-day production 全部通过。
- [x] 启动 F03 Livestock Water source-by-source audit，并拆分 mapped water、verified source、operational status、reliability、capacity、quality、legal access 与 distance metrics。
- [x] 建立 Cow-Calf 与 Sheep F03 narrow relationship candidates；不批准通用距离、每日需水量、容量阈值或物种排名。
- [x] 完成 Mireye v0.14.0 F03 CPER point live audit，确认可提供 hydrography/groundwater/gage context，但不能独立验证 livestock-water adequacy。
- [x] 锁定关键非等价：NHD feature ≠ livestock source；nearest well depth ≠ parcel well yield；straight-line distance ≠ traversable distance；physical water ≠ legal access。
- [x] Runtime-verify USGS NHDPlus parcel queries and NWIS OGC monitoring/groundwater observation queries on CPER.
- [x] 建立 F03 v0.1 data-quality deterministic rules 与 golden tests；remote candidates 只能输出 `NEEDS_VERIFICATION`，missing 输出 `UNKNOWN`。
- [x] 冻结 F03 v0.1 candidate-source inventory 与 parcel-wide Euclidean distance derivation；CPER 共归一化 9 个 mapped candidates，并明确 0 个 verified livestock-water systems。
- [x] 将 F03 接入首个确定性 vertical slice：mapped candidates 只能输出 `NEEDS_VERIFICATION`，不得产生 suitability 或牛羊排名。
- [x] Final-review F03 Cow-Calf 与 Sheep requirements；冻结为 qualitative relationships，移除当前证据不足的 sheep diet-moisture/weather/snow 运行表述。
- [ ] Traversable distance 等待 fencing/barrier/access inputs，不属于 F03 v0.1 完成前置条件。
- [x] 完成 F04 `Soil / Drainage / Ecological Site` 第一阶段 atomicity decision；正式改为 `Soil, Wetness, and Ecological Site Context` Factor family，禁止合并为单一 soil score。
- [x] 建立 F04 首批权威来源与变量清单，区分 map unit/component、drainage、water storage、restrictive layer、salinity、pH、ponding/flooding context 和 ecological-site reference。
- [x] 完成 CPER F04 live data gate：Mireye 7 个 centroid soil fields 成功；官方 SDA 返回 5 个 map units、16 个 components，parcel coverage 在数值容差内为完整。
- [x] 验证 12/16 components 具有 ecological-site linkage，共 6 个 site IDs；该 linkage 仅作解释参考，不代表 current vegetation state 或 suitability。
- [x] 冻结 F04 数据路径：Mireye point 只作 display/QA，官方 SDA parcel polygons/components/horizons 是 primary Land Fact path。
- [x] 验证 6/6 public ecological-site description URLs，并保存 URL、HTTP status 与 response hash。
- [x] 取得 56 条 horizons、16 条 restriction records 和 192 条 monthly wetness records；确认真实 null 必须保持 `UNKNOWN`。
- [x] 冻结 F04 v0.1 derivation contract：map-unit spatial coverage、非归一化 component support weights、controlled-category distributions、参数化 AWC depth integration、restriction censoring、pH 非算术平均和 ecological-site reference boundary。
- [x] 实现并测试 F04 derivation code，并将 data-quality-only deterministic rules 接入 vertical slice；F04=`CONTEXT_DEPENDENT`，`ranking_effect=NONE`，在 species evidence 完成前不允许方向性 signal。
- [x] 更新 CPER Land Profile 与 MatchResult：F01–F04 四 Factor 闭环可执行，牛羊均为 `HOLD`，禁止 cross-profile ranking。
- [x] 修复 F04：EDIT Timeout → `UNKNOWN`（不得标为 `NOT_ACCESSIBLE`）；provenance hash 纳入 horizons；AWC `component_support_coverage_fraction` 仅统计有 AWC overlap 的 component weight。
- [x] 完成四 Factor demo closure：constrained explanation + 本地最小产品面（Parcel Summary / Factor Evidence / Operation Comparison / Unknowns / Diligence Actions / Source Trace）。
- [x] 正式写入 `docs/FACTOR_FREEZE_GATE.yaml` 作为每个 Factor 的统一停止条件。
- [x] 建立 `docs/DEMO_ACCEPTANCE.md`，区分 demo closure implementation 与 demo acceptance。
- [x] 实现极简 geometry replacement 路径（`replace-geometry`），证明 CPER 不是硬编码唯一输入；替换后失效旧 Factor evidence 并改变 hashes。
- [x] 在新增 Factor（含 F05 / Tier 2）前完成 **Four-Factor Demo Acceptance and Reusability Validation** 人工验收。
- [x] 人工检查 demo HTML：HOLD ≠ unsuitable、CONTEXT_DEPENDENT 非正面分、牛羊平级、unknowns/来源可理解、工程 geometry 不误称真实 ranch；当前 HTML 仅作为内部验收面，正式 UI/UX 延后。
- [x] Demo Acceptance 已通过；Tier 2 已获授权，从 Climate/Drought 开始。
- [x] 启动 **F05 Climate and Drought Exposure**：完成第一阶段 atomicity / 边界决策，明确与 Flood、F04 soil-survey wetness、F02/F03 的隔离与允许交互。
- [x] 建立 F05 原子变量候选，并写入 `UNIFIED_LAND_VARIABLE_REGISTRY.yaml`。
- [x] 完成 F05 Mireye v0.14.0 catalog 第一轮审计：可用 `drought_category` / temperature / heat-days；`precipitable_water` 禁止当作降雨；地表年降水需外部 NOAA/PRISM 路径。
- [x] 选择并在 CPER 上 live-test 外部降水路径（主路径 NOAA/NCEI 1991–2020 gridded precip normals；PRISM 仅备选）；同时取得 Mireye point drought/temperature/heat QA；验收为 `LIVE_VERIFIED` / `signal_status: NOT_YET_APPROVED` / `ranking_effect: NONE`（见 `docs/F05_LIVE_DATA_GATE_RESULTS_CPER.md`）。
- [x] 锁定降水架构：NOAA/NCEI Direct Normals NetCDF (`annprcp_norm`) = `CANONICAL_LAND_FACT`；ACIS = `SECONDARY_QA_OR_FALLBACK`（非 canonical）；Mireye = point QA；`345.74 mm` 仅为测量事实。
- [x] 为 Cow-Calf / Sheep 建立 F05 窄关系证据与 requirement（`COW_F05_001` / `SHEEP_F05_001`），并补全 SOURCE_REGISTRY 正式引用；`numeric_rule_status: NOT_APPROVED`。
- [x] 建立 F05 v0.1 data-quality/context deterministic rules 与 golden tests（无虚假阈值）；`ranking_effect: NONE`。
- [x] 将 F05 data-quality/context rules 接入 engine 与 vertical slice；在无阈值前提下输出 `CONTEXT_DEPENDENT` / `NEEDS_VERIFICATION` / `UNKNOWN`；CPER `annprcp_norm=345.74` 保持事实且 `ranking_effect: NONE`；全量测试通过。
- [x] **F05 Freeze Gate PASSED / FROZEN**（`docs/F05_FREEZE_GATE_RESULTS.md`）：按 `FACTOR_FREEZE_GATE.yaml` 逐项确认；Demo Signal/Limitations/Unknowns/Diligence/Source Trace 合格；`HOLD` ≠ 气候不适宜；`345.74 mm` 未转化为负面评价或承载力；geometry replacement 使旧 F05 evidence 失效；全量测试 **63 passed**。
- [x] **F05 milestone 正式关闭**；Five-Factor Portfolio Review 完成（`docs/FIVE_FACTOR_PORTFOLIO_REVIEW.md`）；**F06 尚未选择**。
- [x] 锁定下一步正式目标：**F01–F05 Cross-Parcel and Cross-Environment Validation**（不选 F06）。
- [x] 建立 Cross-Parcel Validation Plan、parcel selection criteria、validation result schema，以及 `test-data/cross-parcel-validation/parcel_registry.yaml`。
- [x] 选定并冻结 5 个工程测试地块填满环境 slots（Konza / CPER / Reynolds / Ordway / KBS MCSE）；preflight 与 registry 冻结后未再换地。
- [x] 对四个新地块统一跑通 Geometry → F01–F05 → Cow/Sheep MatchResult → ValidationResult；五地块 aggregate review 完成。
- [x] **Cross-Parcel Validation PASSED / 结论锁定**（`docs/CROSS_PARCEL_VALIDATION_CONCLUSION.yaml`）：规则跨环境稳定；物种分化尚未建立；主瓶颈为 `F02_COVERAGE_AND_SCOPE` 与 `F03_VERIFIED_WATER`；**F06 = DEFERRED**。
- [x] Flood/Wetness **不得**因与 F05 相邻而自动成为下一项，也不得并入 F05（本轮仍遵守）。
- [x] 锁定下一阶段正式目标：**F02/F03 Evidence Depth and Verification Upgrade**（`docs/F02_F03_EVIDENCE_DEPTH_UPGRADE_PLAN.md`）；优先 F03 verified water，其次 F02 coverage/scope；Mireye SSL 记为独立 adapter incident（`docs/MIREYE_SSL_ADAPTER_INCIDENT_2026-08-08.md`）。
- [x] 建立 F03「候选水体 → 已验证牲畜水源」证据路径（reliability / accessibility / capacity / legal access / seasonal status）；禁止 NHD/距离/遥感直接升格；见 `docs/F03_DEMO_COMPLETION_GATE.yaml`。
- [x] **Demo priority update (product owner)**：`F03 complete → F06 Parcel Configuration → F07 Road and Physical Access → Product Prototype`；**F02 coverage/scope deepening = DEFERRED_FOR_DEMO**（保留现有 limitations 与 runtime）。
- [x] **F06 first-stage audit AUTHORIZED**：原子性/来源审计、derivation spec、deterministic rules、golden tests 已建立；人工确认后授权 deterministic implementation。
- [x] **F06 implementation v0.1**：`src/rangematch/f06_derivation.py` + engine/demo wiring；UTM 投影测量；holes 扣面积；exterior perimeter；international acre 仅为 display；无自动 repair；无阈值、无牛羊 ranking；可执行 golden suite `tests/test_f06_derivation.py`；CPER fixture 已写入。
- [x] **F06 freeze / demo gate PASSED**：FeatureCollection、source CRS 与 lon/lat 边界修复复核通过；`.venv-livegate` 全量 `133 passed`；见 `docs/F06_FREEZE_GATE_RESULTS.md`。
- [x] **F07 first-stage audit APPROVED_V0_1_FOR_IMPLEMENTATION**：人工 corrections 已锁定（TIGER 2025 All Roads canonical；Edges fallback 分版；OSM DEFER；county coverage；INTERSECTS/TOUCHES；tie-break）。
- [x] **F07 implementation v0.1**：`src/rangematch/f07_derivation.py` + `src/rangematch/f07_tiger_adapter.py` + engine/demo wiring；跨县 TIGER 2025 All Roads adapter；CPER live gate `LIVE_VERIFIED`；county coverage PARTIAL/UNKNOWN 不静默测量；INTERSECTS/TOUCHES；distance→LINEARID tie-break；OSM/Edges 未启用；`ranking_effect: NONE`；可执行 suite `tests/test_f07_derivation.py`。
- [x] **F07 freeze / demo gate PASSED**：`docs/F07_FREEZE_GATE_RESULTS.md`；`f07_freeze_status: FROZEN_V0_1`。
- [x] **F07 confirmed-parcel runtime integration**：one-parcel LIVE workflow 调用已冻结 TIGER/Line 2025 All Roads adapter；大体积 road collection 仅留在 cache，Land Profile 只接收 deterministic F07 派生结果；单 Factor 失败独立降级。CPER live investigation gate：county coverage complete、54 mapped features、`INTERSECTS`、nearest `0.0 m`、`ranking_effect: NONE`；Cow/Sheep 仍 peer `HOLD`。
- [x] **F03/F04 confirmed-parcel runtime integration**：F03 通过 USGS NHDPlus HR 建立 mapped-candidate inventory 与 deterministic max-3 review queue；未完成 provenance-complete imagery review 时 `remotely_supported=0`，`field_verified=0`，不把 NHD 映射对象当可用牲畜水源。F04 通过 USDA-NRCS SDA tabular + WFS parcel intersection 生成 soil/wetness/site context，EDIT live access 未审计时保持 UNKNOWN。完整 CPER live gate 无 Factor-local failure：F03 `MAPPED_CANDIDATES_ONLY / NEEDS_VERIFICATION`；F04 coverage complete、`PARCEL_COMPLETE / CONTEXT_DEPENDENT`；investigation `COMPLETED`；Cow/Sheep 仍 `HOLD`，ranking prohibited。
- [x] **One-parcel product acceptance**：真实 React UI → LIVE Mireye coordinate lookup → explicit parcel confirmation → DISCOVERY → F01–F08 → Engine → Unified Output → validated buyer narrative → Evidence/trace 全流程通过；详见 `docs/ONE_PARCEL_PRODUCT_ACCEPTANCE_2026-08-08.md`。验收中修复 UI 未传 `allow_network` / 固定 `BLOCKED_EXTERNAL` 的 live wiring，并将 F03 trace tool 诚实重命名为 `adapter.nhd_water_candidates`。Backend `409 passed`；frontend `20 passed`。下一步锁定为 async investigation job/progress，不改 Factor science。
- [x] **F08 `FROZEN_V0_1`**：data-reuse `PASSED`；全量 `161 passed`；**Demo Factor scope CLOSED**；F09 未授权。
- [x] **阶段切换**：Product Prototype + Agent Orchestration；见 `docs/AGENT_ORCHESTRATION_SPEC.md`。
- [x] **统一输出合同**：`docs/F01_F08_UNIFIED_OUTPUT_CONTRACT.md`（`RANGEMATCH_UNIFIED_OUTPUT@0.1.0`）；可执行 JSON Schema / typed projection 待授权。
- [x] **产品交互边界**：Competition prototype 每次只评估一个 parcel；不做 batch search、portfolio ranking、regional site discovery 或 ICP Finder。
- [x] **用户模式锁定**：Goal-directed 仅按用户意图优先调查选定 Profile；Discovery 对 Cow-Calf / Sheep 平级评估。
- [x] **Mireye prototype workflows**：Property Diligence / lookup、Land Read、Hazards Read；均受 point/diligence semantics、provenance 与 partial-failure gate 约束。
- [x] F08 implementation and freeze：`FROZEN_V0_1`；data-reuse gate passed；full suite `161 passed`。
- [ ] Product Prototype + Agent Orchestration（F01–F08 scope closed；按 AGENT_ORCHESTRATION_SPEC + UNIFIED_OUTPUT_CONTRACT）。
- [x] Executable unified output schema + typed projection（`unified_output.py` + JSON Schema + CPER golden）；不改 Factor 科学规则。
- [x] Packaging strategy locked: Agent runtime first, Skill/submission last; no premature monorepo split (`docs/PACKAGING_AND_DELIVERY_STRATEGY.md`)。
- [x] Planner routing stub (dependency DAG)：`planner.py` + `tool_registry.py` + `PLANNER_ROUTING_SPEC.md` + Mireye adapter contracts；plan-only，无 live network。
- [x] Unified Mireye Context Adapter（offline）：`mireye_adapter.py` + schema + field registry + fixtures/tests；不改 F01–F08 科学。
- [x] Planner executor（fixture-backed）：`planner_executor.py` + `tool_runners.py` + `PLANNER_EXECUTOR_SPEC.md`；无 live network；Mireye 可为 fixture success 或可见 `BLOCKED_EXTERNAL`。
- [x] One-parcel API prototype：`api.py` + `ONE_PARCEL_API_SPEC.md`；fixture / existing Land Profile / parcel resolution。
- [x] Parcel Resolution contract + FIXTURE resolver + API：`parcel_resolution.py` + store + `/v1/parcel-resolutions*`；LIVE `NOT_CONFIGURED`；无 map library。
- [ ] F02 raster coverage upgrade：`DEFERRED_FOR_DEMO`；demo 后重启；现有 `COVERAGE_UNQUANTIFIED` 行为保持不变。
- [ ] 修复 Mireye SSL / SafeBrowse 后仅重跑 point QA / Mireye live gate，不重跑 NOAA/SDA/RAP/NHD canonical 路径。
- [x] Buyer-facing UI on one-parcel API（仍不优先 Docker/Skill）。
- [x] Map UI confirmation on parcel-resolution API（MapLibre GL JS 2D；无 Mapbox token / Cesium / 3D）。

## 1. 系统原则

RangeMatch 是一个受约束的农业土地决策 Agent：

> Fixed, versioned agricultural knowledge defines the rules; physical-world data provides the facts; deterministic, explainable logic evaluates the match; and the LLM plans and explains the investigation without altering the underlying science.

所有实现必须遵守以下边界：

- 农业知识由人工审核、固定并进行版本管理，运行时不可由 LLM 修改。
- 土地事实与分析结论必须分开存储。
- 匹配与评分逻辑必须确定、可复现、可解释。
- LLM 只负责理解意图、制定调查计划、调用工具、组织证据和解释结果。
- LLM 不得创造科学规则、阈值、权重或硬约束。
- 缺失数据必须保持未知，不能自动记为零、通过或失败。
- 只有可靠证据确认硬约束时才可输出 `REJECT`。
- 结果是早期筛查，不代表承载力、盈利能力、投资回报或成功概率。
- 系统必须明确区分 `KNOWN`、`INFERRED`、`UNKNOWN` 和 `NEEDS VERIFICATION`。
- 所有分析必须记录使用的知识、规则、数据和模型版本。
- knowledge design scope、data coverage、initial validation scope、demo scope 和 evidence coverage 必须分别记录；美国数据覆盖不能被误写成全美国已经完成充分科学验证。

### 可扩展的知识结构

```text
Shared Factor Ontology
        +
Base Operation Profiles
        +
Local Land / Environmental Factors
        +
Optional evidence-gated Regional Modifiers
```

- Factor research 和知识架构面向 United States。
- Mireye 当前官方覆盖 United States only，因此美国是现阶段产品数据边界。
- 初始验证集应跨美国多种环境组合；任何单一州都不是默认 validation boundary。
- 地区差异应优先由 climate、soil、vegetation、water、terrain 等 Factor values 表达。
- 只有证据证明 relationship 本身随区域变化时，才可增加局部 Regional Modifier。
- 不采用“一州一套完整 Operation Profile”的默认扩展方式。

### Knowledge Governance — 地理名称规则

> **Geographic names should not substitute for measurable environmental conditions. Climate, terrain, soil, vegetation, water, and drought should be represented as explicit data. State-specific rules should be reserved for policies, legal constraints, or scientifically demonstrated regional relationships that cannot be represented adequately through those factors.**

- 除非某个州本身构成规则适用性的原因，否则不得把州名写进 Scientific Rule。
- Texas 可以是多个 validation regions 之一和 locally applicable evidence 的来源，但不是 scientific identity 或默认 validation geography。
- 证据来自 Texas，不等于 Rule 只能适用于 Texas；必须根据证据内容判断 applicability。
- 地区环境差异优先建模为 Land Factors / Context Variables。
- 法律与政策差异进入 Legal/Policy Diligence Layer，不应混入 biological suitability score。
- 地域性毒草、寄生虫、捕食者和 ecological-site baseline 可以具有地区范围，但必须明确来源与 applicability。

示例：

```text
不要：Texas cattle prefer lower slopes.
要写：Increasing slope can reduce cattle grazing distribution/accessibility.

不要：Texas is drought-prone, so reduce cattle score.
要写：Drought exposure affects forage reliability and grazing risk.

```

任何 Regional Modifier 在进入 reviewed 状态前必须回答：

- 该差异能否由可测量 Factor value 表达？
- 地名是否仅是研究地点？
- 移除地名后，基础 relationship 是否仍成立？
- 是否有证据证明变化的是 relationship 本身？
- 是否其实属于法律或政策，而不是农业生物学？

只要差异可由 Factor values 表达，就不得创建 Regional Modifier。

## 2. 完成标准

MVP 完成时，用户能够提供一块美国土地和可选的目标经营方式，系统可以：

- 识别 Goal-directed 或 Discovery 模式。
- 建立结构化 Land Profile。
- 加载正确版本的 Operation Profile。
- 根据 Profile 自动制定数据调查计划。
- 从 Mireye 及其他受支持来源取得土地事实。
- 对两个 MVP Operation Profile 执行确定性匹配。
- 输出 `ADVANCE`、`REVIEW`、`HOLD` 或 `REDIRECT`。
- 展示强信号、弱信号、硬约束、未知项、证据覆盖率和置信度。
- 在原经营策略匹配较弱时测试替代用途。
- 生成带优先级的下一步尽调清单。
- 为每项结论提供规则和数据来源追踪。
- 在相同输入和版本下产生相同的结构化判断。

## 3. 长期分阶段建设地图与历史审计清单

> 本节保留完整长期路线和历史完成轨迹，不是当前比赛原型必须依次执行的待办列表。当前工作以第 0 节为准。

### Phase 0 — 锁定 MVP 与决策边界

- [ ] 确认 knowledge design 与 data coverage 范围为 United States，initial validation scope 为 selected U.S. regions/reference cases，demo scope 为一个或多个 selected parcels。
- [ ] 确认首批 Operation Profiles：
  - [ ] Cow-Calf Grazing Base Profile
  - [ ] Sheep Grazing Base Profile
- [ ] 为每个 Profile 分别记录 knowledge design scope、data coverage、initial validation scope、demo scope、evidence coverage 和 optional regional modifiers。
- [x] 定义两个输入模式：Goal-directed 与 Discovery（见 `MVP_SPEC.md` 与 `AGENT_ORCHESTRATION_SPEC.md`）。
- [ ] 固定决策标签：`ADVANCE`、`REVIEW`、`HOLD`、`REDIRECT`，以及极少使用的 `REJECT`。
- [ ] 写明产品不能判断的事项，包括精确 carrying capacity、利润、投资回报和法律意见。
- [ ] 定义 MVP 用户主路径： serious ranch buyer/operator 对单块土地进行早期筛查。
- [ ] 建立术语表，统一 Land Profile、Operation Profile、Factor、Rule、Evidence、Constraint、Unknown 等概念。

#### U.S.-wide Validation Design

- [ ] 按 environment × operation 组合选择验证案例，不以州界作为抽样框架。
- [ ] 首批 6–10 个案例覆盖 Great Plains cattle、rugged Intermountain grazing、western sheep、humid Southeast pasture、drought constraint 和 flood/wetness constraint。
- [ ] Texas 可以提供一个 Demo parcel 或部分案例，但只是 one validation region among several。
- [ ] 在 Land Profile 中保留 ecological/rangeland region 字段。
- [ ] 将 `Base Profile + local Land Factors + optional ecological/rangeland Regional Modifier` 设为知识层成熟后的演进方向。
- [ ] 跨环境验证用于发现明显外推错误，不得被描述为已经证明全美普遍有效。

**交付物**

- MVP scope document
- Decision-label specification
- Product limitations statement
- Domain glossary

### Phase 1 — 建立固定 Agricultural Knowledge Layer

执行原则：Phase 1 的完整内容属于长期 ontology backlog。当前 Demo 范围已锁定为 Cow-Calf 和 Sheep 两个平级 Profiles 共用的 `F01–F08` 八个 Factor families；不得在 Demo 前启动 F09 或更后面的 Factor。权威范围见 `docs/DEMO_FACTOR_SCOPE.md`。

#### 1.1 Factor Ontology

- [ ] 建立 Factor 的统一数据结构。
- [ ] 为每个 Factor 分配稳定 `factor_id`。
- [ ] 建立完整 ontology backlog（不等于全部进入比赛 MVP）：
  - [ ] Terrain / slope / elevation
  - [ ] Grass cover / shrub cover / forage condition
  - [ ] Soil / drainage / ecological site
  - [ ] Surface water / groundwater evidence / water distribution
  - [ ] Rainfall / drought / flood / heat / wildfire
  - [ ] Acreage / shape / fragmentation
  - [ ] Road and legal access
  - [ ] Fencing / infrastructure / utilities
  - [ ] Predator exposure / poisonous plants
  - [ ] Water rights / zoning / permits
- [ ] 每个 Factor 记录定义、单位、意义、数据源、远程可判断性、缺失行为和限制。
- [ ] 明确哪些 Factor 是 observed、derived、user-provided 或 field-only。
- [ ] Factor research 以美国放牧系统为证据检索范围，并为每项 evidence 保存 geographic applicability。
- [ ] State-specific evidence 必须显式标记，不能默认提升为 United States-wide relationship。
- [x] 锁定两个 Profiles 共用的八个 Demo Factor families（F01–F08），只有该集合进入当前 Demo；F09+ 全部延期。
- [ ] 为 shared Factor 保持统一定义和 Land Fact，并在两个 Operation Profiles 中分别定义 relationship、importance、constraint logic 和 evidence。
- [ ] 对未进入首批子集的 Factors 标记优先级和延期原因，不在比赛版中做浅层、无证据的规则。

#### 1.2 Scientific Rule Library

- [ ] 定义 Rule schema：operation、factor、关系、重要性、规则类型、解释逻辑、地理适用性和限制。
- [ ] 区分：
  - [ ] Hard constraint
  - [ ] Suitability factor
  - [ ] Context-dependent factor
  - [ ] Verification-only factor
- [ ] 只在权威证据支持时使用数值阈值。
- [ ] 为每条规则建立 human-review 状态。
- [ ] 禁止在运行时新增或修改规则。

#### 1.3 Operation Profile Library

- [ ] 以 `Animal + Production Model` 定义 Base Profile，不把 Texas 或州名写入 Profile identity。
- [ ] 为两个 MVP Profile 选择适用 Factors 和 Rules。
- [ ] 定义每个 Factor 在各 Profile 中的作用、权重或优先级。
- [ ] 定义各 Profile 的最低证据覆盖要求。
- [ ] 建立 semantic versioning，并保留变更记录。
- [ ] 分析结果必须保存 `operation_profile_version`。
- [ ] 分别保存 `knowledge_design_scope`、`data_coverage_scope`、`initial_validation_scope`、`demo_scope` 和 `evidence_coverage`。
- [ ] 仅在证据证明 relationship 本身发生区域变化时添加版本化 Regional Modifier。

#### 1.4 Evidence Registry

- [ ] 收集 USDA、NRCS、multi-state Extension、USGS、NOAA、FEMA、relevant state agencies 和同行评审研究。
- [ ] 每项证据记录来源机构、标题、作者、年份、URL、地区、证据强度和备注。
- [ ] 将每条 Scientific Rule 关联到一项或多项证据。
- [ ] 建立证据质量与冲突处理标准。
- [ ] 对过期、地区不适用或证据薄弱的规则进行标记。
- [ ] 为 `applicability` 使用受控分类：`United States`、`Multi-region U.S.`、`Ecological-site-specific`、`Regional`、`State-policy-specific`。
- [ ] 禁止把州名作为默认 applicability 标签；只有确实不能超出某州且原因已记录时，才在 `Regional` 或 `State-policy-specific` 下进一步注明州名。
- [ ] 分开记录 `study_location` 与 `rule_applicability`，避免把研究地点误当成规则边界。

#### 1.5 Limitations Registry

- [ ] 建立系统能力限制的结构化清单。
- [ ] 为 water rights、well yield、fencing、actual forage productivity 等定义默认未知行为。
- [ ] 定义何时输出 `UNKNOWN` 与 `NEEDS VERIFICATION`。
- [ ] 为每类限制生成对应的现场核查建议。

#### 1.6 Verified Operation Reference Set

> 优先级：轻量 validation set 提前；完整 similarity engine 延后。Reference Cases 用于发现明显违反现实的规则或权重，但不作为最优土地用途的 ground truth。

- [ ] 在继续大规模 Coding 前选出 6–10 个 U.S. 可核验案例，覆盖不同环境组合和经营方式。
- [ ] 验证集至少包含：
  - [ ] cattle-dominant cow-calf operation
  - [ ] sheep operation 或 sheep-dominant mixed rangeland
  - [ ] mixed-livestock operation
  - [ ] 具有已知 grazing constraints 的困难土地
- [ ] 运行验证时仅向系统提供 parcel/location，不向 Agent 暴露实际 operation 标签。
- [ ] 执行 Known-operation validation：实际用途至少应被模型判断为 reasonable fit；若不一致，先检查 Profile、Factor、Rule 和 weight。
- [ ] 执行 Cross-use validation：确认系统不会对所有土地机械推荐 cattle，并能因土地差异产生不同 operation rankings。
- [ ] 不要求现实中的 operation 必须获得最高分，因为现实选择还受经营者偏好、市场、基础设施、劳动力、融资和历史路径影响。
- [ ] 将案例标记为 `Verified Operation Reference Case`，禁止标记为 `Ground Truth Optimal Land Use`。
- [ ] 核心闭环验证后再定义完整 Reference Case schema。
- [ ] 只收录经营类型和位置等信息可核验的案例。
- [ ] 保存土地特征、经营类型、核验来源、数据完整性和适用范围。
- [ ] 明确案例只用于 sanity check、comparable analysis、解释和未来校准。
- [ ] 禁止把案例相关性解释成因果关系或科学规则。

**交付物**

- Versioned Factor Library
- Versioned Scientific Rule Library
- Two reviewed Operation Profiles
- Evidence and Limitations registries
- 6–10 case validation set（完整 reference dataset 与 similarity engine 延后）

### Phase 2 — 审计并接入土地数据

- [ ] 获取并审计 Mireye 的实际字段目录、API、覆盖范围、单位、分辨率和 provenance。
- [ ] 建立 `Factor → Data Source → Field` 映射表。
- [ ] 避免重复获取 Mireye 已经提供的数据。
- [ ] 识别缺口，并选择最少数量的补充权威数据源。
- [ ] 优先补充 drought、rainfall、wells、flood、water/legal records 等关键数据。
- [ ] 定义用户上传 listing、survey、water records 和其他文件的输入方式。
- [ ] 为每个 connector 实现错误、限流、超时和数据不可用处理。
- [ ] 建立缓存和 freshness 策略。
- [ ] 保存每项事实的 source、fetched_at、resolution、freshness 和 confidence。
- [ ] 建立测试 parcel 集合，覆盖不同地形、植被、水源和风险组合。

**交付物**

- Mireye field audit
- Factor-to-source coverage matrix
- Data connector specifications
- Test parcel dataset

### Phase 3 — 建立 Land Intelligence Layer

- [ ] 定义规范化 Land Profile schema。
- [ ] 建立 parcel identity、geometry 和 acreage 的统一处理。
- [ ] 统一单位、坐标系、时间范围和分类体系。
- [ ] 支持 point、parcel、buffer、raster summary 等不同空间粒度。
- [ ] 为原始值与 derived facts 分别保存 provenance。
- [ ] 检测数据冲突、过期、覆盖不完整和低分辨率情况。
- [ ] 保存 unresolved unknowns，而不是用默认值填补。
- [ ] 将用户或 seller 提供的 claim 与 verified fact 分开存储。
- [ ] 使 Land Profile 可复用，但允许按 freshness 更新事实。
- [ ] 明确禁止把 LLM 文本结论写入 Land Facts。

**交付物**

- Land Profile schema
- Normalization pipeline
- Provenance and confidence model
- Land Profile API/storage layer

### Phase 4 — 建立确定性 Matching Engine

- [ ] 定义输入：`Land Profile × Operation Profile Version`。
- [ ] 定义 Factor evaluation 的标准输出。
- [ ] 实现 hard-constraint evaluation。
- [ ] 实现 positive、negative、neutral、context-dependent 和 unknown 状态。
- [ ] 实现规则优先级、权重和可解释的聚合方法。
- [ ] 将 Evidence Coverage 与 Suitability 分开计算。
- [ ] 数据不足时降低 confidence 或输出 `HOLD`，而不是生成虚假精确度。
- [ ] 定义决策标签的确定性映射规则。
- [ ] 实现两个 Profile 的横向比较。
- [ ] 实现 `REDIRECT`：当前 Profile 较弱时评估其他受支持 Profile。
- [ ] 生成 machine-readable reason codes。
- [ ] 保存完整决策追踪：输入事实、规则版本、中间判断和最终标签。
- [ ] 建立 golden tests，保证相同输入与版本得到相同结果。
- [ ] 做 sensitivity test，确认单个权重不会产生不合理翻转。

**交付物**

- Deterministic rule evaluator
- Explainable suitability aggregation
- Decision-label engine
- Cross-profile redirect engine
- Golden test suite

### Phase 5 — 建立 Agent Planning 与工具编排

权限边界：Planner 只能决定“从哪里取已批准 Factor 的数据、先查什么、何时复用缓存、失败后如何重试或标记未知”。Planner 无权决定“农业上还应该看什么”，也不得因为 LLM 临时想到新指标而扩展 Operation Profile。

- [ ] 定义 User Intent schema。
- [ ] 解析位置、parcel、目标 operation、用户约束和上传资料。
- [ ] 由 Operation Profile 生成所需 Factor 清单。
- [ ] 将 Operation Profile 生成的 Factor 清单视为本次调查允许访问的科学维度白名单。
- [ ] 将 Factors 分类为 cached、Mireye、external、user-provided 和 field-only。
- [ ] 只调用完成判断所需要的数据源。
- [ ] 支持工具失败后的重试、降级和未知标记。
- [ ] 禁止 Agent 绕过 Profile 自行加入未经批准的科学维度。
- [ ] Agent 如发现可能有价值的新 Factor，只能记录为人工审核候选，不得用于当前 MatchResult。
- [ ] 禁止 Agent 修改规则、阈值或权重。
- [ ] 为每次运行保存 investigation plan 和 tool-call audit trail。
- [x] 为 Discovery 模式规划两个 Profile 的共享 Land Profile 与数据获取，避免重复调用。

**交付物**

- Intent parser
- Investigation planner
- Tool orchestration workflow
- Runtime guardrails and audit logs

### Phase 6 — 建立 LLM 解释层

- [ ] 只向 LLM 提供经过结构化的 facts、rule results、citations 和 limitations。
- [ ] 使用结构化输出 schema，禁止自由生成最终分数。
- [ ] 要求每个重要结论绑定事实和规则。
- [ ] 明确标注 `KNOWN`、`INFERRED`、`UNKNOWN`。
- [ ] 生成 Strong Signals、Weak Signals、Constraints 和 Unknowns。
- [ ] 解释为什么当前策略得到该判断。
- [ ] 解释为什么替代策略可能更合适。
- [ ] 生成按风险和信息价值排序的 diligence actions。
- [ ] 加入禁止性提示：不得声称利润、承载力、法律确定性或保证成功。
- [ ] 检测 LLM 输出与确定性结果是否冲突；冲突时以 engine 为准并记录错误。
- [ ] 建立 hallucination、citation 和 unsupported-claim 测试。

**交付物**

- Structured explanation schema
- Grounded explanation prompts
- Output validator
- LLM evaluation suite

### Phase 7 — 产品体验与报告

- [ ] 建立土地输入与地图/parcel 选择流程。
- [x] 产品输入合同允许用户选择目标经营方式，或进入 Discovery 模式；UI implementation 属于当前 prototype 阶段。
- [ ] 展示 Agent 的调查计划和数据获取进度。
- [ ] 设计决策摘要，而不是只显示单一分数。
- [ ] 展示 Profile 比较及 `REDIRECT` 逻辑。
- [ ] 展示每项结论的数据来源和知识证据。
- [ ] 清楚展示未知信息与现场验证事项。
- [ ] 提供可下载或可分享的尽调报告。
- [ ] 在 UI 中持续显示“preliminary screening”限制说明。
- [ ] 允许用户纠正 parcel、补充文件或标记已核实事实后重新运行。

**建议报告结构**

1. Property and intended strategy
2. Decision label
3. Preliminary suitability and evidence coverage
4. Strong signals
5. Weak signals and constraints
6. Known / inferred / unknown
7. Alternative supported uses
8. Prioritized diligence actions
9. Sources, versions and limitations

### Phase 8 — 验证、专家审核与安全性

- [ ] 邀请来自不同美国 grazing environments 的 rangeland、livestock 或 Extension 专家审核两个 Profiles。
- [ ] 让专家审核硬约束、权重、术语和限制声明。
- [ ] 使用 verified operations 做 sanity check，而不是直接训练结论。
- [ ] 构造边界案例、冲突数据、缺失数据和工具失败测试。
- [ ] 测试地域外土地是否被系统正确拒绝或标记不支持。
- [ ] 测试 prompt injection，确保上传文件不能修改科学规则。
- [ ] 测试 source spoofing 和低质量来源混入。
- [ ] 测量 deterministic consistency、evidence coverage 和 citation correctness。
- [ ] 记录错误类别并建立人工复核流程。
- [ ] 未通过专家审核前，不把系统描述成权威农业建议。

**发布门槛**

- [ ] 两个 Operation Profiles 均完成人工审核。
- [ ] 所有生产规则均有证据或明确标记为 expert judgment。
- [ ] 所有结果均可追踪到事实与规则版本。
- [ ] 未知数据不会被静默填补。
- [ ] 关键场景的 golden tests 全部通过。
- [ ] LLM 不能改变 engine 输出。
- [ ] 报告中不存在无证据的精确数值或保证性陈述。

### Phase 9 — MVP 上线与反馈闭环

- [ ] 选择少量真实 ranch buyer/operator 进行封闭测试。
- [ ] 记录用户是否理解决策标签、证据和未知项。
- [ ] 测量是否减少无效现场考察或缩短初筛时间。
- [ ] 收集用户后续取得的现场验证结果。
- [ ] 将反馈作为 Knowledge Layer 更新候选，而不是运行时自动学习。
- [ ] 通过人工审核发布新的 Profile 或 Rule 版本。
- [ ] 保留旧版本，确保历史报告可复现。
- [ ] 根据使用频率评估一次性报告、短期订阅和专业 SaaS 模式。

## 4. 推荐实施顺序

不要先做完整聊天界面。推荐按以下顺序完成最小垂直切片：

1. 一个 selected U.S. 测试 parcel。
2. 固定的八个 shared Factor families（F01–F08）。
3. 两个平级的轻量 Operation Profiles。
4. 三组基于相同 Land Facts、带证据且可产生不同解释的确定性 Rules。
5. 一个规范化 Land Profile。
6. 一个纯代码 Matching Engine。
7. 一个结构化结果 JSON。
8. 加入跨 Profile 比较和 `REDIRECT`。
9. 加入一个只解释既有结果的 LLM 层。
10. 最后完善交互、报告和更多数据连接。

**比赛版锁定的最小闭环**

> Selected U.S. parcel → F01–F08 shared Factor families → Cow-Calf/Sheep peer Profiles → Mireye/少量外部数据 → deterministic matches → unknowns → cross-profile comparison → REDIRECT → LLM explanation

完整 ontology、完整 Verified Operation Reference Set、Benchmark Similarity Engine 和所有 Phase 的生产级能力，均不作为该闭环出 Demo 的前置条件。

第一条可演示的完整路径应为：

```text
User goal + selected U.S. parcel
        ↓
Load user-selected Profile or both peer Profiles
        ↓
Create investigation plan
        ↓
Fetch and normalize land facts
        ↓
Run deterministic matching
        ↓
Preserve and expose unknowns
        ↓
Compare supported alternatives if needed
        ↓
Return REDIRECT when an alternative is materially stronger
        ↓
LLM explains grounded results
        ↓
Decision + evidence + unknowns + next diligence
```

## 5. 核心数据实体

- `FactorDefinition`
- `ScientificRule`
- `OperationProfile`
- `EvidenceRecord`
- `LimitationRecord`
- `ReferenceOperation`
- `Parcel`
- `LandFact`
- `LandProfile`
- `UserIntent`
- `InvestigationPlan`
- `FactorEvaluation`
- `MatchResult`
- `AlternativeUseComparison`
- `DiligenceAction`
- `AnalysisRun`

每个可版本化实体至少需要：

- Stable ID
- Version
- Status (`draft`, `reviewed`, `deprecated`)
- Created/updated timestamps
- Reviewer or provenance
- Change notes

## 6. 历史第一轮待办事项与里程碑记录

> 本节记录项目早期建设顺序。它不再表示当前下一步；当前下一步见第 0.8 节。

- [ ] 创建项目目录与基础技术架构。
- [ ] 将本文档登记为项目的 canonical build plan。
- [ ] 建立 Factor、Rule、Evidence、Operation Profile 的 schema。
- [x] 锁定两个平级 Profiles 共享的 F01–F08 八个 Demo Factor families（见 `docs/DEMO_FACTOR_SCOPE.md`）。
- [ ] Collect the first authoritative U.S.-applicable evidence set for Cow-Calf and Sheep relationships for each candidate Factor.
- [ ] 分开记录每项 evidence 的 `study_location` 与 `rule_applicability`。
- [ ] State-specific evidence 只用于 locally relevant validation、ecological context，或有证据支持且不能由普通 Factor values 表达的 regional relationship。
- [ ] 从 `F01 Terrain & Slope` 开始逐 Factor 建立正式 Evidence Registry，不再继续扩写无来源追踪的 Factor summary。
- [ ] 审计 Mireye 字段并建立覆盖矩阵。
- [ ] 选择一个测试 parcel。
- [ ] 选出 6–10 个跨环境、跨 operation 的 U.S. Verified Operation Reference Cases。
- [ ] 为验证集预先写明 Known-operation 与 Cross-use validation protocol，避免看到结果后改变评价标准。
- [ ] 手工构建第一个 Land Profile fixture。
- [ ] 实现不依赖 LLM 的规则计算原型。
- [ ] 为原型建立 golden tests。
- [ ] 再接入 LLM 生成受约束的调查解释。

### 当前阶段状态：端到端比赛原型已完成；进入 Packaging / Deployment Readiness；F09 NOT_AUTHORIZED

```yaml
backend_tests: 423_PASSED
ui_tests: 22_PASSED
llm_intent_and_buyer_report: IMPLEMENTED
report_validator: HARDENED_WITH_ADVERSARIAL_TESTS
deterministic_ui_fallback: IMPLEMENTED
parcel_resolution_contract: IMPLEMENTED
parcel_resolution_api: IMPLEMENTED_FIXTURE_AND_LIVE
parcel_map_ui: IMPLEMENTED_MAPLIBRE_2D
mireye_live_parcel_resolver_contract: DOCUMENTED
mireye_lookup_parcel_adapter: IMPLEMENTED_FIXTURE_AND_LIVE
parcel_resolver_live_http: LIVE_VERIFIED_ON_CLEAN_NETWORK
public_diligence_search: IMPLEMENTED_WITH_OFFICIAL_SOURCE_CITATIONS
buyer_report_v2: IMPLEMENTED_DASHBOARD_READABLE_REPORT_APPENDIX
next_slice: COMPETITION_PACKAGING_AND_DEPLOYMENT_READINESS
engine_behavior: HOLD_ONLY_NO_APPROVED_RANKING
```

Governance note:

```text
Regrid licensing answers do NOT block competition Demo.
They only block long-term commercial cache / redistribution / owner PII display.
Catalog compatibility gate: IMPLEMENTED (offline fixture + gated LIVE fetch).
Lookup HTTP transport: IMPLEMENTED (allow_network gated; injectable for tests).
Historical SafeBrowse interception remains documented; current clean-network live path is verified. Any recurrence must remain a visible `BLOCKED_EXTERNAL` state.
```

Demo priority (product owner):

```text
F03 complete
→ F06 Parcel Configuration
→ F07 Road and Physical Access
→ F08 Woody and Shrub Vegetation Structure
→ Product Prototype
```

- F03 evidence-depth upgrade: **COMPLETE** — [`F03_DEMO_COMPLETION_GATE.yaml`](./F03_DEMO_COMPLETION_GATE.yaml)
- F02 coverage upgrade: **DEFERRED_FOR_DEMO** — preserve existing limitations/runtime; do not deepen before demo
- F06 Parcel Configuration: **FROZEN_V0_1** — `docs/F06_FREEZE_GATE_RESULTS.md`
- F07: **FROZEN_V0_1** — `docs/F07_FREEZE_GATE_RESULTS.md`; live gate `LIVE_VERIFIED`
- F08: **FROZEN_V0_1** — data-reuse gate passed；Demo Factor scope CLOSED

F08 retained audit and freeze artifacts:

- [`F08_WOODY_SHRUB_ATOMICITY_AND_SOURCE_AUDIT.md`](./F08_WOODY_SHRUB_ATOMICITY_AND_SOURCE_AUDIT.md)
- [`F08_DATA_SOURCE_AND_MIREYE_AUDIT.yaml`](./F08_DATA_SOURCE_AND_MIREYE_AUDIT.yaml)
- [`F08_WOODY_SHRUB_DERIVATION_SPEC.yaml`](./F08_WOODY_SHRUB_DERIVATION_SPEC.yaml)
- [`F08_WOODY_SHRUB_DETERMINISTIC_RULES.yaml`](./F08_WOODY_SHRUB_DETERMINISTIC_RULES.yaml)
- [`F08_WOODY_SHRUB_GOLDEN_TESTS.yaml`](./F08_WOODY_SHRUB_GOLDEN_TESTS.yaml)

F08 checklist:

- [x] Factor boundary vs F02 / non-equivalences drafted
- [x] RAP SHR/TRE proposed canonical; Mireye point QA only; LCMS/NLCD parcel aggregate deferred
- [x] Shared F02/F08 RAP acquisition/coverage design drafted
- [x] Atomic vs derived variables decided; browse/obstruction rejected; spatial/temporal change deferred
- [x] Data-quality deterministic rules drafted (`CONTEXT_DEPENDENT` / `NEEDS_VERIFICATION` / `UNKNOWN`; `ranking_effect: NONE`)
- [x] Golden-test contract drafted and executable
- [x] Human review of first-stage audit package — PASSED
- [x] Implementation code and freeze — `FROZEN_V0_1`
- [ ] F09+ — blocked until after Demo

F07 artifacts:

- [`F07_ROAD_PHYSICAL_ACCESS_ATOMICITY_AND_SOURCE_AUDIT.md`](./F07_ROAD_PHYSICAL_ACCESS_ATOMICITY_AND_SOURCE_AUDIT.md)
- [`F07_DATA_SOURCE_AUDIT.yaml`](./F07_DATA_SOURCE_AUDIT.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml`](./F07_ROAD_PHYSICAL_ACCESS_DERIVATION_SPEC.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_DETERMINISTIC_RULES.yaml`](./F07_ROAD_PHYSICAL_ACCESS_DETERMINISTIC_RULES.yaml)
- [`F07_ROAD_PHYSICAL_ACCESS_GOLDEN_TESTS.yaml`](./F07_ROAD_PHYSICAL_ACCESS_GOLDEN_TESTS.yaml)
- Implementation: `src/rangematch/f07_derivation.py`
- Adapter: `src/rangematch/f07_tiger_adapter.py`
- Executable suite: `tests/test_f07_derivation.py`
- CPER live gate: [`F07_LIVE_DATA_GATE_RESULTS_CPER.md`](./F07_LIVE_DATA_GATE_RESULTS_CPER.md)
- CPER roads fixture: `test-data/live-results/cper/f07_tiger2025_all_roads_search_window.geojson`
- CPER result: `test-data/live-results/cper/f07_derivation_result_2026-08-08.json`

F07 checklist:

- [x] Factor boundary / non-equivalences drafted (`mapped road ≠ legal access`, etc.)
- [x] Canonical source locked: US Census TIGER/Line 2025 All Roads; Edges separately versioned FALLBACK; OSM DEFER from v0.1
- [x] Atomic vs derived variables decided; legal/network/seasonal items deferred
- [x] Exact contact/distance formulas approved (INTERSECTS vs TOUCHES; county coverage; tie-break)
- [x] Data-quality deterministic rules approved (`CONTEXT_DEPENDENT` / `NEEDS_VERIFICATION` / `UNKNOWN`; `ranking_effect: NONE`)
- [x] Golden-test contract approved and executable; includes cross-county coverage + equal-distance tie-break
- [x] Human review of first-stage audit package — PASSED with locked corrections
- [x] Implementation code — v0.1 complete (engine + CPER TIGER 2025 fixture + golden suite)
- [x] F07 freeze / demo gate — PASSED (`FROZEN_V0_1`)
- [x] F08 freeze — FROZEN_V0_1; demo scope CLOSED; orchestration spec drafted

F06 artifacts:

- [`F06_PARCEL_CONFIGURATION_ATOMICITY_AND_SOURCE_AUDIT.md`](./F06_PARCEL_CONFIGURATION_ATOMICITY_AND_SOURCE_AUDIT.md)
- [`F06_PARCEL_CONFIGURATION_DERIVATION_SPEC.yaml`](./F06_PARCEL_CONFIGURATION_DERIVATION_SPEC.yaml)
- [`F06_PARCEL_CONFIGURATION_DETERMINISTIC_RULES.yaml`](./F06_PARCEL_CONFIGURATION_DETERMINISTIC_RULES.yaml)
- [`F06_PARCEL_CONFIGURATION_GOLDEN_TESTS.yaml`](./F06_PARCEL_CONFIGURATION_GOLDEN_TESTS.yaml)
- Implementation: `src/rangematch/f06_derivation.py`
- Executable suite: `tests/test_f06_derivation.py`
- CPER result: `test-data/live-results/cper/f06_derivation_result_2026-08-08.json`

F06 checklist:

- [x] Factor boundary / non-equivalences / CRS policy audited
- [x] Atomic vs derived variables decided; redundant metrics deferred
- [x] Exact formulas proposed before implementation
- [x] Data-quality deterministic rules drafted (`CONTEXT_DEPENDENT` / `NEEDS_VERIFICATION` / `UNKNOWN`; `ranking_effect: NONE`)
- [x] Golden tests drafted and executable
- [x] Human review of first-stage audit package — PASSED; formulas, CRS policy, v0.1 no-auto-repair policy, rules, and golden-test contract approved
- [x] Implementation code — v0.1 complete (engine + CPER fixture + golden suite)
- [x] Input-boundary patch — FeatureCollection exactly-one Feature; source_crs EPSG:4326 only; lon/lat bounds checks
- [x] F06 freeze / demo gate — PASSED after input-boundary recheck
- [x] F07 first-stage audit package — APPROVED_V0_1_FOR_IMPLEMENTATION; human corrections locked
- [x] F07 implementation — IMPLEMENTED_V0_1
- [x] F07 freeze / demo gate — PASSED (`FROZEN_V0_1`)
- [x] F08 freeze gate — PASSED; AGENT_ORCHESTRATION_SPEC drafted; no F09
- [x] F01–F08 unified output contract drafted (`F01_F08_UNIFIED_OUTPUT_CONTRACT.md`)
- [x] Executable unified output schema + typed projection (no Factor science changes)
- [x] Planner DAG stub against unified output stages (assemble→evaluate→project→explain)
- [x] Unified Mireye Context Adapter offline slice (still no Factor science changes)
- [x] Planner executor fixture-backed slice；随后接入 controlled live paths（未改 Factor science）
- [x] One-parcel API orchestration on top of fixture executor
- [x] Constrained LLM Intent Parser
- [x] Constrained LLM Buyer Report Generator
- [x] Deterministic Report Validator, including adversarial grounding tests
- [x] Buyer-facing Dashboard + Readable Report + Evidence Appendix
- [x] Address/coordinate parcel resolution and explicit 2D boundary confirmation
- [x] Async one-parcel investigation job + truthful Planner trace progress UI
- [x] Async acceptance for single-process demo (`ASYNC_INVESTIGATION_JOB_ACCEPTANCE_2026-08-08.md`)
- [x] SafeStructure-inspired cohesive intake → map confirmation → mode selection → Agent progress UX (`design-qa.md` passed)
- [x] Buyer report visual hierarchy aligned to the same product system: decision-first hero, report navigation, buyer narrative, peer operation cards, and collapsed technical evidence (`design-qa.md` passed)
- [ ] Durable shared investigation store / job queue for multi-worker deployment
- [x] Controlled live OpenAI Buyer Report acceptance gate on public CPER fixture (`OPENAI_LIVE_GATE_RESULTS_2026-08-08.md`); product-owner authorization recorded and backend-configured live narrative enabled
- [x] Diligence Search Agent v0.1: bounded public-source topics, .gov/.edu source gate, Responses API web search, citations, fixture/API tests, and live Weld County gate; side branch only with `effect_on_engine: NONE`
- [x] Diligence Search UI integration: automatic post-analysis run, visible Public Diligence Agent progress, buyer-readable current-guidance section, clickable source cards, and fail-open report behavior
- [ ] Deployment packaging and production environment validation
- [x] F08 implementation and freeze — `FROZEN_V0_1`; data-reuse gate passed; no F09+ work is permitted before the Demo

F03 closure (retained):

- [x] Contract / evaluator / five-parcel remote collection / synthetic field ingestion / demo completion gate
- [x] Live parcels `field_verified_count: 0`; synthetic TEST_ONLY isolated

## 7. 文档维护规则

- 本文档是 RangeMatch Agent 建设工作的基准清单。
- 新需求应先判断是否符合“固定知识、土地事实、确定性匹配、LLM 规划与解释”的系统原则。
- 完成任务后勾选对应项目，并在必要时补充交付物链接。
- 任何科学规则、硬约束或评分变更，都必须经过证据补充、人工审核和版本升级。
- 如果实现与本文档冲突，应先更新并说明决策，而不是静默偏离。
- Research backup 只作为 Factor、数据源与证据候选线索；必须经过原始来源恢复和人工审核后，才能进入 Evidence Registry 或 Scientific Rule Library。
- Knowledge Governance 的地理名称规则属于硬性约束；任何例外必须记录无法由 Land Factors 表达的原因、证据和人工审核决定。
