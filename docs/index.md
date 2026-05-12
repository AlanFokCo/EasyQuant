# EasyQuant Docs

EasyQuant 是一个面向 **中国 A 股市场** 的事件驱动量化回测与策略开发框架，核心包为 [`eqlib`](https://github.com/AlanFokCo/EasyQuant/tree/main/eqlib)。

站点整合了项目文档中心、教程系列和 API 参考，方便按学习路径快速跳转。

<div class="grid cards" markdown>

-   :material-rocket-launch: **Quick Start**

    ---

    安装依赖、跑通第一份回测、打开 HTML 报告。

    [开始上手](doc/user_guide.md)

-   :material-book-open-page-variant: **User Manual**

    ---

    阅读用户手册、报告指标说明、FAQ 与适配器文档。

    [进入文档中心](doc/README.md)

-   :material-school: **Tutorials**

    ---

    从 Tutorial 00 到 Tutorial 10，按步骤学习回测、优化与实盘流程。

    [浏览教程](tutorials/README.md)

-   :material-api: **API Reference**

    ---

    查看 API 索引、完整参考和 `eqlib.utils` 工具库说明。

    [打开 API 文档](doc/api_index.md)

</div>

## 常用入口

- [项目仓库](https://github.com/AlanFokCo/EasyQuant)
- [中文 README](README_zh.md)
- [Examples 代码索引](examples/Examples.md)
- [报告与指标详解](doc/reports_and_metrics.md)

## 本地预览

```bash
pip install -e ".[docs]"
mkdocs serve
```

启动后访问 <http://127.0.0.1:8000>。
