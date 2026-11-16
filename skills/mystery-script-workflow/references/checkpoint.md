# 续做记录

优先复用现有状态文件；没有时建 `制作进度.json` 及简短入口。完成状态来自具体产物和验收，不由进程启动、目录存在或文件计数推定。下列结构可调整，不强制旧项目迁移schema：

```json
{
  "project": "作品名称",
  "updated_at": "实际ISO时间及偏移",
  "requested_scope": ["archive", "dm", "simulation", "audio"],
  "active_stage": "archive",
  "source_index": "相对路径/资料索引.md",
  "source_revision": "版本或清单哈希",
  "archive": {
    "manifest": "相对路径/转换清单.json",
    "source_files": 0,
    "physical_pages": 0,
    "transcribed_pages": 0,
    "visually_reviewed_pages": 0,
    "open_issues": [],
    "next_document": "待处理文件",
    "next_physical_page": 1
  },
  "dm": {"index": null, "completed_stages": [], "open_questions": []},
  "simulation": {
    "status": "not_started",
    "round": null,
    "release_ledger": null,
    "last_public_event": null,
    "received_submissions": [],
    "waiting_for": [],
    "isolation_method": null,
    "adopted_rule_supplements": []
  },
  "audio": {
    "manifest": null,
    "reviewed_chapters": [],
    "finished_chapters": [],
    "voice_reference": null,
    "qa_report": null
  },
  "next_action": "一个可直接执行的小步骤",
  "blockers": []
}
```

源哈希变化先找受影响页、证据、发放包与对白，保留旧版并重核依赖，不直接宣告全部成果无效或沿用旧页码。声音模板变化按配音技能指纹规则处理。

模拟从确认的发放账、公开事件及实例上下文恢复；待收回答不当已收到。实例丢失时只重建其已知范围并记录，不能补写“先前真实发言”。

输出尽量原子保存，下一步记为某份材料/一幕/有意义的缺口。旧脚本可记参考路径，状态本身不包含自动执行命令、凭据或未经授权的外部操作。
