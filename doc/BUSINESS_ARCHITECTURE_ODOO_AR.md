# معمارية الأعمال (Business Architecture) ومنصّة Odoo
# مطابقة ميتاموديل Business Architecture Guild v3.0 على Odoo

> الملف المرفوع `business_architecture_metamo.pdf` هو **«دليل ميتاموديل معمارية الأعمال
> v3.0»** (Business Architecture Guild، سبتمبر 2024) — المرجع المعياري الذي يعرّف **مجالات
> معمارية الأعمال (Domains)** وعلاقاتها على أسس تصميم رسمية.
>
> هذه الوثيقة تطابق **مجالات معمارية الأعمال العشرة** على **Odoo**، وتجيب لكلٍّ: ما تعريفه؟
> أين يقع في Odoo؟ وهل **يُعكَس من الكود** (ربطاً بـ `REVERSE_ENGINEERABLE_FROM_CODE_AR`
> و`METADATA_LIMITS_AR`)؟ ثمّ موقعه في **ورشة Fit-to-Standard** (`EA_FIT_TO_STANDARD_AR`).

---

## 1. مجالات معمارية الأعمال (من الدليل v3.0)

الدليل يعرّف معمارية الأعمال كـ**قاعدة معرفة (Knowledgebase)** من مجالات مترابطة، تُعرَض
عبر **مخطّطات (Blueprints)** و**سيناريوهات**. المجالات الأساسية:

| # | المجال (Domain) | السؤال الذي يجيبه |
|---|------------------|--------------------|
| 5.1 | **Value Stream** (تدفّق القيمة) | كيف تُسلَّم القيمة للمستفيد عبر مراحل؟ |
| 5.2 | **Capability** (القدرة) | ماذا تستطيع المنشأة أن تفعل؟ |
| 5.3 | **Information** (المعلومات) | ما الكائنات/المفاهيم المعلوماتية؟ |
| 5.4 | **Organization** (التنظيم) | مَن (وحدات/أدوار)؟ |
| 5.5 | **Stakeholder** (صاحب المصلحة) | لمن القيمة / مَن المعنيّ؟ |
| 5.6 | **Strategy** (الاستراتيجية) | لماذا / إلى أين؟ |
| 5.7 | **Initiative** (المبادرة) | بماذا نغيّر (مشاريع/برامج)؟ |
| 5.8 | **Policy** (السياسة) | بأيّ قواعد وضوابط؟ |
| 5.9 | **Product** (المنتج) | ماذا نقدّم؟ |
| (5.10) | **Value/Metric** (القيمة/المقياس) | بماذا نقيس النجاح؟ |

---

## 2. المطابقة على Odoo + قابلية العكس

| المجال | تعريفه (الدليل) | أين في Odoo | يُعكَس؟ |
|--------|------------------|-------------|:------:|
| **Value Stream** | تسلسل مراحل تُنتج قيمة للمستفيد | تدفّق المستندات `sale→stock→account` + `base.automation` (EPC) | ◐ استنتاج |
| **Capability** | قدرة مستقرّة (ما تفعله المنشأة) | الموديول + `category` + تصنيف نماذج القيمة (chain/shop/network) | ◐ استنتاج |
| **Information** | المفاهيم/الكائنات المعلوماتية | كائنات `ir.model`: `res.partner`, `product.template`, `account.move` | ✅ آلي |
| **Organization** | الوحدات والأدوار | `res.company` / `res.groups` / `res.users` | ✅ آلي |
| **Stakeholder** | الأطراف المعنيّة بالقيمة | `res.partner` (عميل/مورّد) + `mail.followers` | ✅/◐ |
| **Strategy** | الأهداف والتوجّه | — (نيّة بشرية، ليست في الكود) | ✗ |
| **Initiative** | المشاريع/البرامج المُحوِّلة | `project.project` (كتمثيل) — لا كتصريح استراتيجي | ◐ |
| **Policy** | القواعد والضوابط | `ir.rule` + قواعد `base.automation` + `ir.config_parameter` | ◐ |
| **Product** | ما تقدّمه المنشأة | `product.template` (+ السمات/المتغيّرات) | ✅ آلي |
| **Value/Metric** | مقاييس القيمة | تقارير/`*.report` + المحاسبة التحليلية + KPIs | ◐ |

> القاعدة (من `METADATA_LIMITS_AR`): المجالات «ماذا/مَن» (Information, Organization,
> Product) **تُعكَس آلياً**؛ مجالات «كيف» (Value Stream, Capability, Policy) **تُستنتَج**؛
> مجال «لماذا» (Strategy) **لا يُعكَس** — قرار بشري.

---

## 3. المجالات الأربعة الأساسية بالتفصيل (الأكثر صلةً بـ Odoo)

### ٣.١ Capability (القدرة) — «ماذا تفعل»
الدليل: قدرة مستقرّة لا تتغيّر بتغيّر العملية أو التنظيم. في Odoo: **كل تطبيق يجسّد
قدرات** (Sales = «إدارة المبيعات»، Inventory = «إدارة المخزون»). تُستخرَج تلميحاً من
`category` ونماذج الموديول (revres facts) وتُصنَّف عبر نماذج القيمة و APQC. لكن **خريطة
القدرات الرسمية** (Capability Map) قرار بشري يُبنى فوق هذا التلميح.

### ٣.٢ Value Stream (تدفّق القيمة) — «كيف تُسلَّم القيمة»
الدليل: مراحل تُراكم القيمة من **محفّز** إلى **قيمة مُسلَّمة** للمستفيد. في Odoo: **تدفّق
المستندات** هو التجسيد التشغيلي — «من عرض السعر إلى النقد» = `sale.order → stock.picking →
account.move`. يُعكَس بنيوياً (الاعتماديات + `base.automation`) لكن **ربطه بمستفيدٍ وقيمةٍ
استراتيجية** بشري (راجع نماذج القيمة الثلاثة).

### ٣.٣ Information (المعلومات) — «أيّ كائنات»
الدليل: مفاهيم معلوماتية مستقرّة (Information Concepts) لا تفاصيل تقنية. في Odoo: **هي
بالضبط الكائنات التجارية** في `ir.model` — `res.partner` (طرف)، `product.template` (منتج)،
`account.move` (قيد). **يُعكَس آلياً بالكامل** عبر revres (`models[]/fields[]` = ERM).
هذا أقوى تطابق بين الدليل و Odoo.

### ٣.٤ Organization (التنظيم) — «مَن»
الدليل: وحدات تنظيمية وأدوار. في Odoo: `res.company` (الوحدة)، `res.groups` (الدور/
الصلاحية)، `res.users` (الشخص). **يُعكَس آلياً** عبر موديول `base` والأمان.

---

## 4. العلاقات (Associations) — جوهر الميتاموديل

قوّة الدليل في **ربط المجالات** (Cross-mapping). تتجسّد في Odoo كعلاقات فعلية:

| علاقة الدليل | تجسيدها في Odoo |
|---------------|------------------|
| Capability ↔ Value Stream | الموديول يمكّن مرحلةً في تدفّق المستندات |
| Value Stream ↔ Information | كل مرحلة تقرأ/تكتب كائنات (`sale.order` يحمل `partner_id`, `order_line`) |
| Capability ↔ Information | القدرة تعمل على كائنات (`account` ↔ `account.move`) |
| Organization ↔ Capability | المجموعة (`res.groups`) تملك القدرة (صلاحيات الموديول) |
| Stakeholder ↔ Value Stream | `res.partner` هو المستفيد في نهاية التدفّق |
| Policy ↔ Capability | `ir.rule`/`base.automation` تضبط سلوك القدرة |

> هذه العلاقات **مُستخرَجة جزئياً** من revres (العلاقات بين النماذج، الاعتماديات،
> الأمان)، وهي ما يجعل قاعدة معرفة معمارية الأعمال **قابلة للملء من Odoo** لا رسماً يدوياً.

---

## 5. الموقع في ورشة Fit-to-Standard

كل مجال يخدم مرحلةً (ربطاً بـ `EA_FIT_TO_STANDARD_AR §4`):

```
Capability + Value Stream  → ① تحديد نموذج القيمة + ② اختيار العمليات القياسية
Information + Organization  → ③ عرض الكائنات والأدوار القياسية حيّاً (run-odoo)
Product                    → ④ تهيئة المنتج (Fit) — PRODUCT_CONFIGURATION_AR
Policy + Metric            → ④ ضبط القواعد والمقاييس
Strategy + Initiative      → بشري: يربط الورشة بأهداف العميل ومشاريعه
Stakeholder                → ⑤ القبول (مَن يوقّع على Fit/Gap)
```

**الخلاصة العملية:** المجالات القابلة للعكس (Information/Organization/Product) تُملأ آلياً
من revres فتُسرّع الورشة؛ والمجالات الاستنتاجية (Capability/Value Stream/Policy) تُلمَّح
ثم تؤكَّد بشرياً؛ والمجالات البشرية (Strategy/Initiative) تبقى مُدخلاً من العميل.

---

## 6. الخلاصة

- **دليل v3.0** يعرّف معمارية الأعمال كقاعدة معرفة من **عشرة مجالات** مترابطة
  (Value Stream, Capability, Information, Organization, Stakeholder, Strategy, Initiative,
  Policy, Product, Metric).
- **في Odoo:** Information/Organization/Product **تُعكَس آلياً** (أقوى تطابق:
  Information = `ir.model`)؛ Capability/Value Stream/Policy/Metric **تُستنتَج** (نماذج
  القيمة + APQC + revres)؛ Strategy/Initiative **بشرية** لا تُعكَس.
- **العلاقات** بين المجالات تتجسّد كعلاقات Odoo فعلية (نماذج/اعتماديات/أمان) — فتُملأ
  قاعدة المعرفة جزئياً من الكود.
- **في Fit-to-Standard:** المجالات القابلة للعكس تُسرّع بناء «القياسي»، والاستنتاجية
  تُلمَّح وتؤكَّد، والبشرية تبقى مُدخل العميل.

باختصار: ميتاموديل معمارية الأعمال هو **العدسة الرسمية للطبقة العليا**، وOdoo يملأ نصفها
آلياً (الكائنات والتنظيم والمنتج) ويُلمّح للنصف الآخر (القدرات وتدفّقات القيمة) — وهذا
بالضبط ما يربط معمارية الأعمال بمعمارية التطبيقات في مستودع Fit-to-Standard.

---

*المصادر: «The Business Architecture Metamodel Guide v3.0» (Business Architecture Guild،
2024)؛ مطابقة على Odoo عبر `ir.model`/`res.*`/`product.template`/`ir.rule`؛ مكمّلة لـ
`REVERSE_ENGINEERABLE_FROM_CODE_AR`، `METADATA_LIMITS_AR`، `VALUE_MODELS_THREE_AR`،
`APQC_PCF_VALUE_MODELS_AR`، `EA_FIT_TO_STANDARD_AR`. Odoo 19.0.*
