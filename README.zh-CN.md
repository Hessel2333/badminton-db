# BadmintonDB · 羽毛球装备资料库

为装备记录 App、资料查询和社区项目提供独立、开放、可追溯的装备数据。

[English](README.md) · [API 文档](docs/API.md) · [数据模型](docs/DATA_MODEL.md) · [贡献指南](CONTRIBUTING.md) · [许可范围](LICENSES.md)

## 初版内容

v0.1.0 包含 **10 个品牌、73 款装备**：46 款羽毛球、20 款球拍、7 款球鞋，以及 **69 条图片元信息**。原有装备 UUID 全部保留。

这是从现有装备目录整理出的首批数据。所有型号目前标记为“未核验”；没有依据的规格留空。原目录中的参考价格保留为“无明确观察日期的历史参考值”，不表示当前市场价格。

## 数据和图片

- 每个型号一个 JSON 文件，便于提交补充和纠错。
- 记录中英文名称、型号、别名、系列、版本信息及来源。
- 型号资料与个人购买、库存、消耗、备注分离；本仓库不包含用户业务数据或备份。
- 图片记录种类、尺寸、校验值、来源与处理方式，以及独立的授权状态。
- **初版不公开分发图片文件**：69 条图片记录均为 `withheld`，下载地址为空，等待确认可再分发授权。
- 15 款 Victor 图标记为包装重建渲染图，其固定示意条码 `1234567890128` 不作为真实商品条码或货号。

## 使用

静态 JSON API，无需 API Key：

```text
https://hessel2333.github.io/badminton-db/v1/manifest.json
https://hessel2333.github.io/badminton-db/v1/products/index.json
https://hessel2333.github.io/badminton-db/v1/catalog.json
https://hessel2333.github.io/badminton-db/exports/ios/equipment_catalog.json
```

需要固定版本或离线使用时，从 [Releases](https://github.com/Hessel2333/badminton-db/releases) 下载数据包并核对 `SHA256SUMS`。

`schemaVersion` 标识 API 结构，`dataVersion` 标识数据发布版本，`catalogVersion` 用于兼容现有 iOS 目录升级。`v1` API 随最新数据更新；历史版本以 Release 为准。

## 本地维护

需要 Python 3.11 或更高版本：

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -r requirements.txt
python scripts/catalog.py validate
python -m unittest discover -s tests -v
python scripts/catalog.py build
python scripts/catalog.py package
```

`dist/` 自动生成 API、JSON Schema、校验值和 iOS 导出；`output/` 生成 ZIP 发布包。两者不手工维护，也不提交 Git。GitHub Actions 会检查数据、运行测试并发布 `main` 的静态 API。

iOS 导出保留现有 UUID、图片键及历史参考价格，不会用空下载地址替换 App 内已有图片。购买和库存等用户资料继续由 App 本地管理。详见 [iOS 接入说明](docs/IOS.md)。

## 贡献与许可

欢迎补充官网来源、型号信息、明确的别名和获得授权的图片。提交图片时需说明权利人、许可证、授权依据和处理历史；不能把下载来源当成再分发许可。校验程序会拒绝未经批准的图片文件进入发布包。

代码、校验工具、Schema 和文档使用 MIT；我们原创的数据组织与整理使用 CC BY 4.0；图片逐项单独许可。许可范围不覆盖第三方图片和品牌商标的权利，详见 [LICENSES.md](LICENSES.md)。

项目借鉴 AppleDB 的公共资料库模式，羽痕 iOS 是初始数据来源与首个使用场景。现有目录导入记录见 [migration.json](docs/migration.json)。
