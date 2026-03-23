# Arkham Address Scraper

通过 Arkham Intelligence 抓取实体关联地址的 Web 工具。

## 本地运行

```bash
pip install -r requirements.txt
python app.py
```

访问 http://localhost:5000

## 部署到 Railway（推荐）

1. 注册 [Railway](https://railway.app)
2. New Project → Deploy from GitHub Repo
3. 选择本仓库，Railway 自动识别 Dockerfile 并部署
4. 部署完成后获得公开 URL，发给组员即可

## 使用方法

1. 输入 Arkham 账号密码登录（首次需要，之后 cookie 保留 7 天）
2. 输入 Entity ID（如 `excoino`、`nobitex`、`wallex-ir`）
3. 选择链和最低金额
4. 点击 Run Scrape
5. 结果可直接筛选，或 Export CSV

## 注意事项

- 服务器使用 headless Chrome，每个用户 session 独立
- gunicorn 设置单 worker（`-w 1`），避免多个 Chrome 实例撑爆内存
- 单次抓取上限 2000 条 offset，如需更多修改 `app.py` 中的限制
