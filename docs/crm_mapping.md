# intel_tags → CRM 标签映射表（S5-INTEL-017）

industry 维度全部 14 个标签的 CRM 映射如下。CRM 中**找不到对应标签**的项单独列在
「待确认（missing）」清单，不由本工单自行创建，待核心团队确认后补充。

## 已映射（12 项）

| industry code | 名称 | crm_tag_code |
|---|---|---|
| manufacturing | 制造业 | crm_ind_manufacturing |
| software | 软件与信息技术服务 | crm_ind_software |
| biopharma | 生物医药 | crm_ind_biopharma |
| new_energy | 新能源 | crm_ind_new_energy |
| new_materials | 新材料 | crm_ind_new_materials |
| smart_equipment | 智能制造装备 | crm_ind_smart_equipment |
| food_beverage | 食品饮料 | crm_ind_food |
| textile_apparel | 纺织服装 | crm_ind_textile |
| building_materials | 建材家居 | crm_ind_building |
| commerce_logistics | 商贸物流 | crm_ind_logistics |
| financial_services | 金融服务 | crm_ind_finance |
| professional_services | 专业服务 | crm_ind_professional |

## 待确认（missing，2 项）

| industry code | 名称 | 说明 |
|---|---|---|
| agriculture | 现代农业 | CRM 行业标签无农业类目，建议新增 crm_ind_agriculture |
| culture_tourism | 文化旅游 | CRM 行业标签无文旅类目，建议新增 crm_ind_culture |

## normalize 规则

industry code 与 CRM 标签编码比对前统一转小写并去空白；两侧编码不一致时
在映射表标注 normalize 规则，不做静默匹配。
