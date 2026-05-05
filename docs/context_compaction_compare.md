# 当前对话上下文压缩与 `claudecode` 的详细差异

## 目的

本文对比当前简化版实现与 `claudecode` 在“对话上下文过大”场景下的处理方式，重点说明：

- 当前项目已经实现了什么
- `claudecode` 还做了哪些更完整的处理
- 两者行为差异会带来什么结果
- 后续如果继续靠近 `claudecode`，应优先补哪一层

对比基线：

- 当前项目主逻辑：[scc/agent.py](F:\code\easycode\scc\agent.py:102)
- `claudecode` 主循环：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:365)
- `claudecode` 工具结果预算控制：[claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:922)

## 总体结论

当前项目的实现属于“轻量预处理”：

- 在请求前压缩超大的 `tool_result`
- 在请求前把过长历史折叠成一条摘要边界消息

`claudecode` 的实现属于“多层上下文治理”：

- 先处理工具结果预算
- 再做 snip / microcompact / context collapse / autocompact
- 如果 API 仍返回 prompt-too-long，再做恢复性 compact 重试
- 整个过程带有稳定状态、缓存一致性、失败保护和恢复路径

因此，当前实现能显著降低“多轮后上下文爆炸”的概率，但还不是 `claudecode` 那种严格、可恢复、可持续多轮运行的完整方案。

## 一、处理链路差异

### 1. 当前项目：两步预处理

当前项目在每轮请求前调用 [scc/agent.py](F:\code\easycode\scc\agent.py:237)：

1. `_apply_tool_result_budget()`  
   位置：[scc/agent.py](F:\code\easycode\scc\agent.py:113)

2. `_compact_history_if_needed()`  
   位置：[scc/agent.py](F:\code\easycode\scc\agent.py:187)

然后把处理后的 `messages_for_query` 发给模型：  
[scc/agent.py](F:\code\easycode\scc\agent.py:284)

这个链路是同步、本地、启发式的，目标很直接：在真正请求模型前，尽量把上下文字符数压下来。

### 2. `claudecode`：多层治理链路

`claudecode` 在主循环里对上下文的处理顺序更细：

1. `getMessagesAfterCompactBoundary()`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:365)

2. `applyToolResultBudget()`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:379)

3. `snipCompactIfNeeded()`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:403)

4. `microcompact(...)`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:414)

5. `contextCollapse.applyCollapsesIfNeeded(...)`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:441)

6. `autocompact(...)`  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:454)

7. 如果模型仍报 prompt-too-long，再进入恢复路径  
   位置：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1063)

差别不在“有没有压缩”，而在“是不是分层、可恢复、状态稳定”。

## 二、`tool_result` 压缩差异

### 1. 当前项目：内容裁剪

当前项目对 `role == "tool"` 的消息直接按字符数裁剪，逻辑在：

- [scc/agent.py](F:\code\easycode\scc\agent.py:113)
- [scc/agent.py](F:\code\easycode\scc\agent.py:140)

行为特点：

- 不区分工具类型
- 不区分是否已经被模型看过
- 不持久化原始内容
- 只保留头尾，中间替换为 `... (snipped) ...`

优点：

- 简单、立即见效
- 对当前 Python 结构侵入小

限制：

- 每次都是就地改写消息
- 裁剪后的结果不可回溯到原始输出
- 没有“稳定替换决策”的机制

### 2. `claudecode`：预算控制 + 持久化 + 稳定替换

`claudecode` 的 `applyToolResultBudget()` 核心不只是“截短”，而是：

- 先按“每条消息中的工具结果总量”判断是否超预算  
  位置：[claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:768)

- 选择最大的新鲜结果替换  
  位置：[claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:674)

- 把完整结果落盘，只把预览和文件引用给模型  
  位置：[claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:137)

- 用 `seenIds` / `replacements` 固定决策，保证后续轮次字节级稳定  
  位置：[claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:390)

这带来几个当前项目没有的特性：

- 同一个 `tool_use_id` 以后总是同一种替换结果
- 不会因为“这次压了、下次没压”破坏缓存前缀
- 可以恢复旧会话时继续沿用原来的压缩决策

### 3. 直接差异结论

当前项目是“把大结果裁短”。  
`claudecode` 是“把大结果替换成稳定引用，并把完整结果放到上下文外”。

这意味着：

- 当前项目减少了 token，但牺牲了可恢复性和稳定性
- `claudecode` 不只是省 token，还在维护长期会话的一致性

## 三、历史压缩差异

### 1. 当前项目：前缀替换成摘要

当前项目会在总字符数超过阈值时：

- 保留最近 `SCC_KEEP_LAST_MESSAGES` 条消息
- 把更早消息折叠成一个 assistant 摘要
- 避免 payload 以孤立的 `tool` 消息开头

相关实现：

- [scc/agent.py](F:\code\easycode\scc\agent.py:154)
- [scc/agent.py](F:\code\easycode\scc\agent.py:187)
- [scc/agent.py](F:\code\easycode\scc\agent.py:218)

当前摘要内容很轻：

- 丢弃消息数量
- 粗略字符量
- 历史里最多 4 条用户消息摘要

这是“静态摘要替换”。

### 2. `claudecode`：多层历史治理

`claudecode` 不是一次性把旧消息摘要掉，而是按不同层次处理：

- `snipCompactIfNeeded()`：先剪掉一部分历史负担  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:403)

- `microcompact(...)`：对消息结构做更细粒度压缩  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:414)

- `contextCollapse.applyCollapsesIfNeeded(...)`：做“可持续的上下文折叠视图”  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:441)

- `autocompact(...)`：真正生成 compact 后的消息集  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:454)

并且 compact 完成后会重新构造 `postCompactMessages`：  
[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:528)

### 3. 直接差异结论

当前项目的历史压缩是：

- 一次性的
- 基于字符数
- 不区分消息语义层级

`claudecode` 的历史压缩是：

- 分阶段的
- 同时考虑消息结构、预算、后续恢复
- 不只是“缩短”，而是“管理上下文视图”

这意味着：

- 当前项目更容易丢失重要中间状态
- `claudecode` 更擅长长期、多工具、多轮推理的上下文保真

## 四、失败恢复差异

### 1. 当前项目：没有 reactive compact

当前项目的预处理全部发生在请求发出之前。  
如果请求仍然因为 prompt-too-long、HTTP 413、服务端拒绝等失败：

- 当前逻辑不会基于这次失败再做二次压缩
- 也不会自动进入“压缩后重试”路径

当前主循环在 API 错误时直接返回：  
[scc/agent.py](F:\code\easycode\scc\agent.py:310)

### 2. `claudecode`：失败后恢复

`claudecode` 会在模型返回 prompt-too-long 后分两步恢复：

1. 先尝试 `contextCollapse.recoverFromOverflow(...)`  
   [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1094)

2. 再尝试 `reactiveCompact.tryReactiveCompact(...)`  
   [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1118)

如果恢复成功，会生成新的 `postCompactMessages` 并继续当前 query loop：  
[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1146)

如果恢复失败，才把错误真正暴露出来：  
[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1166)

### 3. 直接差异结论

当前项目是“请求前尽量压，压不住就失败”。  
`claudecode` 是“请求前先压，失败后还能恢复再试一次”。

这对长会话影响很大：

- 当前项目在极限上下文下更脆
- `claudecode` 更接近生产可用的弹性行为

## 五、状态管理差异

### 1. 当前项目：无持久状态

当前项目的压缩状态只存在于 `self.messages` 当前内容中：

- 没有 replacement state
- 没有 compact tracking
- 没有“已经压缩过哪些 tool_result”的独立记录

也就是说，当前消息本身就是全部状态。

### 2. `claudecode`：显式状态

`claudecode` 至少维护了这些状态层：

- `ContentReplacementState`  
  [claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:390)

- auto compact tracking  
  相关使用点：[claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:367), [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:521)

- compact 之后的 post-compact message set  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:528)

这使它可以：

- 跨轮次保持决策一致
- 避免重复 compact 抖动
- 支持 resume / fork / sidechain 继续工作

## 六、预算计算差异

### 1. 当前项目：字符估算

当前项目的判断依据是字符数估算：

- 单消息大小估算：[scc/agent.py](F:\code\easycode\scc\agent.py:102)
- tool result 阈值：`SCC_MAX_TOOL_RESULT_CHARS`
- 历史阈值：`SCC_MAX_CONTEXT_CHARS`

这适合简化版，但它不是 token 级预算。

### 2. `claudecode`：更接近 token 级治理

`claudecode` 明确围绕 token / blocking limit / compact budget 做控制：

- `tokenCountWithEstimation(...)`  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:638)

- blocking limit 判断  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:592)

- compact 后预算延续  
  [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:504)

这比单纯字符数更稳，因为不同内容的 token 密度差异很大。

## 七、当前实现已经解决了什么

相对改造前，当前项目已经解决了两个最主要的问题：

1. 大型工具输出不再无限累计进上下文  
   位置：[scc/agent.py](F:\code\easycode\scc\agent.py:113)

2. 长历史不会原样全部带进下一轮  
   位置：[scc/agent.py](F:\code\easycode\scc\agent.py:187)

这足以明显降低：

- 多轮后响应越来越慢
- 若干轮后请求超时
- 因大 `tool_result` 导致上下文暴涨

## 八、当前实现还缺什么

和 `claudecode` 相比，当前项目还缺的关键层如下。

### 1. 缺少稳定 replacement state

缺失影响：

- 同一段结果的压缩决策不具备可追踪性
- 长会话里可能存在“压缩前后语义波动”

对照实现：

- [claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:390)

### 2. 缺少持久化的大结果引用机制

缺失影响：

- 当前被裁掉的中间内容彻底消失
- 模型无法通过引用路径重新读取完整内容

对照实现：

- [claudecode/src/utils/toolResultStorage.ts](F:\code\easycode\claudecode\src\utils\toolResultStorage.ts:137)

### 3. 缺少分层 compact

缺失影响：

- 一旦超限，只能做“粗摘要替换”
- 无法像 `microcompact` / `contextCollapse` 那样按结构保留更多信息

对照实现：

- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:403)
- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:414)
- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:441)

### 4. 缺少失败后的恢复性重试

缺失影响：

- 一旦仍然超限，只能失败返回
- 无法自动再 compact 一层后重试

对照实现：

- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1063)
- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:1118)

### 5. 缺少 token 级预算

缺失影响：

- 字符数和真实 token 开销不完全一致
- 阈值需要更保守

对照实现：

- [claudecode/src/query.ts](F:\code\easycode\claudecode\src\query.ts:638)

## 九、对当前项目行为的实际影响

从运行效果上看，两者差异会体现在以下方面：

1. 短到中等长度会话  
   当前项目已经够用，能明显改善第 8 到第 15 轮附近的上下文膨胀问题。

2. 长会话、多工具、高输出任务  
   `claudecode` 会更稳，因为它不是只做一次裁剪，而是有分层 compact 和失败恢复。

3. 可恢复性  
   当前项目一旦裁掉中间信息，后续无法找回；`claudecode` 可以通过持久化结果和稳定状态维持一致性。

4. 缓存与一致性  
   `claudecode` 明确在保护 prompt cache 的稳定前缀；当前项目没有这层能力。

## 十、如果继续向 `claudecode` 靠近，建议优先级

如果后续要继续演进，建议优先顺序如下：

1. 给 `tool_result` 增加“落盘引用”而不是只做头尾截断  
   这是收益最高的一层。

2. 引入独立的 replacement state  
   让压缩决策跨轮次稳定下来。

3. 增加“失败后 reactive compact 重试”  
   解决“请求前压了但仍然超限”的问题。

4. 把字符预算改成 token 预算  
   让阈值更准确。

5. 逐步拆成 snip / microcompact / collapse 多层  
   这是最接近 `claudecode` 的方向，但工程量最大。

## 附：当前实现入口

当前项目上下文压缩的入口和关键点如下：

- 请求前统一预处理：[scc/agent.py](F:\code\easycode\scc\agent.py:237)
- 发给模型的消息集构造：[scc/agent.py](F:\code\easycode\scc\agent.py:284)
- `tool_result` 压缩：[scc/agent.py](F:\code\easycode\scc\agent.py:113)
- 历史上下文压缩：[scc/agent.py](F:\code\easycode\scc\agent.py:187)

## 文档结论

当前项目已经具备了“简化但有效”的上下文压缩能力，核心价值在于把最容易膨胀的两部分先拦下来：

- 大工具输出
- 过长对话历史

但与 `claudecode` 相比，当前方案仍是“预处理型压缩”，而不是“分层治理 + 稳定状态 + 失败恢复”的完整上下文管理体系。

一句话概括：

当前项目解决的是“别让上下文太快爆掉”。  
`claudecode` 解决的是“上下文变大时如何持续、稳定、可恢复地运行下去”。
