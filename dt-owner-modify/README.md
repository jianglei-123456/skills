# dt-owner-modify — 大田修改机主 / 经销商

给定一批 IMEI、目标机主，可选目标经销商：

- **机主**：`ysb.install_iot_owner.customer_id` → `ysb.customer.id`
- **经销商**（给了 `--distributor` 才改）：`install_iot_owner.distributor_id`、`install_iot.company_id`、
  `install_iot.install_distributor_company_id`、`install_iot_machine.distributor_id`、
  `public.iot.owner_company_id/owner_company`（machine 库）、`contract.iot.owner_company_id/owner_company`（dss 库）
- 最后逐台调用 DSS `/dtwl/sales/install/pushData`（与 `push_ysb.py` 相同）把数据推到平台

## 前置

- `dbx` CLI，连接 `prod_192.168.5.17_machine`（需允许写）、`prod_192.168.5.129_dss_owner`
- 环境变量 `DT_USERNAME` / `DT_PASSWORD`

```bash
python scripts/check_env.py
```

## 用法

```bash
# 1) 预查询（只读）—— 把输出给用户看，确认后再往下走
python scripts/preview.py --imeis "673555585146926,673555585138721" \
  --owner "安徽省农垦集团淮南农场有限公司" --distributor "寿县大唐农机销售有限公司"

# 2) 拿 token
TOKEN=$(python scripts/get_token.py)

# 3) 执行（改库 + 同步）
python scripts/update_owner.py --imeis "673555585146926,673555585138721" \
  --owner "安徽省农垦集团淮南农场有限公司" --distributor "寿县大唐农机销售有限公司" \
  --token "$TOKEN" --yes
```

`--owner` / `--distributor` 都可给 id 或名称（名称支持部分匹配）。只改机主时省略 `--distributor`。
未加 `--yes` 只做校验、不写库。
