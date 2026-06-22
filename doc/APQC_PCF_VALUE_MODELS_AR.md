# الربط بين إطار APQC PCF (الإكسل) ونماذج القيمة الثلاثة
# (Linking the APQC Process Classification Framework to the Three Value Models)

> الملف المرفوع `K08897_CrossIndustry_v721_vs_v611` هو **إطار APQC PCF لتصنيف العمليات
> عبر الصناعات** (Cross-Industry Process Classification Framework)، إصدار 7.2.1 مقابل
> 6.1.1. يضمّ **13 فئة** عمليات في تسلسل هرمي (فئة → مجموعة عمليات → عملية → نشاط).
>
> هذه الوثيقة تربط فئات APQC الـ13 بـ **نماذج القيمة الثلاثة** (السلسلة/المتجر/الشبكة)
> وبتمييز **الأساسية/الداعمة** وبوحدات **Odoo** — وتقدّم **برومبت (Prompt) جاهزاً** لتصنيف
> أي عملية من الإكسل آلياً. مكمّلة لكل وثائق القيمة على هذا الفرع.

---

## 1. بنية إطار APQC PCF (من الإكسل)

13 فئة، مقسومة كما في الإكسل إلى مجموعتين — **وهذا التقسيم يطابق تمييز الأساسية/الداعمة**:

### العمليات التشغيلية (Operating) = أقرب للأنشطة **الأساسية**
| الفئة | الاسم | مجموعات فرعية |
|------|-------|---------------|
| 1.0 | Develop Vision and Strategy | 5 |
| 2.0 | Develop and Manage Products and Services | 4 |
| 3.0 | Market and Sell Products and Services | 6 |
| 4.0 | **Deliver Physical Products** | 5 |
| 5.0 | **Deliver Services** | 4 |
| 6.0 | Manage Customer Service | 6 |

### الإدارة والخدمات الداعمة (Management & Support) = الأنشطة **الداعمة**
| الفئة | الاسم | مجموعات فرعية |
|------|-------|---------------|
| 7.0 | Develop and Manage Human Capital | 10 |
| 8.0 | Manage Information Technology (IT) | 8 |
| 9.0 | Manage Financial Resources | 12 |
| 10.0 | Acquire, Construct, and Manage Assets | — |
| 11.0 | Manage Enterprise Risk, Compliance… | — |
| 12.0 | Manage External Relationships | 6 |
| 13.0 | Develop and Manage Business Capabilities | 9 |

> **الملاحظة المفتاحية:** APQC يفصل أصلاً بين «التشغيلية» و«الداعمة» تماماً كما يفصل
> Porter/Stabell بين «الأساسية» و«الداعمة». فالربط طبيعي ومباشر.

---

## 2. الربط الجوهري: فئة APQC للتسليم تحدّد النموذج

أوضح ربط هو أن **فئة التسليم في APQC تطابق نموذج القيمة**:

| فئة APQC | نموذج القيمة | لماذا |
|----------|--------------|-------|
| **4.0 Deliver Physical Products** | **السلسلة 🏭** | تحويل مدخلات → منتج مادي (long-linked) |
| **5.0 Deliver Services** | **المتجر 🧑‍⚕️** | تقديم خدمة/حلّ مشكلة (intensive) |
| **6.0 Manage Customer Service + 12.0 External Relationships** | **الشبكة 🔗** | ربط ووساطة بين أطراف (mediating) |

أي أن اختيار المنشأة لفئة التسليم (4.0 أم 5.0 أم 6.0) في APQC **هو نفسه** اختيار نموذج
القيمة.

---

## 3. الربط الكامل: APQC ↔ النموذج ↔ النشاط ↔ Odoo

| فئة APQC | النوع | النموذج المرتبط | النشاط (Porter/Stabell) | وحدة Odoo |
|----------|------|------------------|--------------------------|-----------|
| 1.0 الرؤية والاستراتيجية | أساسي (تمكين) | الكل | البنية التحتية | `account`, لوحات القيادة |
| 2.0 تطوير المنتجات/الخدمات | أساسي | الكل | تطوير التكنولوجيا | `product`(BoM/سمات), `project` |
| 3.0 التسويق والبيع | أساسي | الكل | التسويق والمبيعات | `crm`, `sale`, `website` |
| **4.0 تسليم منتجات مادية** | أساسي | **السلسلة** | لوجستيات·عمليات | `purchase`,`mrp`,`stock` |
| **5.0 تسليم الخدمات** | أساسي | **المتجر** | اكتشاف·حلّ·تنفيذ | `project`,`hr_timesheet` |
| **6.0 خدمة العملاء** | أساسي | **الشبكة** | تقديم الخدمة/الوساطة | `helpdesk`Ⓔ,`website`,`payment` |
| 7.0 رأس المال البشري | داعم | الكل | الموارد البشرية | `hr*` |
| 8.0 تقنية المعلومات | داعم | الكل (حرِج للشبكة) | تطوير التكنولوجيا | البنية التقنية, `bus` |
| 9.0 الموارد المالية | داعم | الكل | البنية التحتية | `account*` |
| 10.0 الأصول | داعم | الكل | البنية التحتية | `maintenance`, `account_asset`Ⓔ |
| 11.0 المخاطر والامتثال | داعم | الكل | البنية التحتية | `approvals`, قواعد `ir.rule` |
| 12.0 العلاقات الخارجية | داعم | الشبكة | ترويج الشبكة/العقود | `sign`, `purchase`, شركاء |
| 13.0 قدرات الأعمال | داعم | الكل | تطوير التكنولوجيا | `knowledge`Ⓔ, `base.automation` |

---

## 4. ⭐ البرومبت الجاهز (Prompt) لتصنيف عمليات الإكسل آلياً

استخدم هذا البرومبت مع أي نموذج لغوي لتصنيف **أي صف** من إطار APQC PCF (من الإكسل) إلى
نموذج قيمة + نشاط + وحدة Odoo:

```text
أنت محلّل عمليات أعمال خبير في إطار APQC PCF ونماذج تكوين القيمة
(Stabell & Fjeldstad) ونظام Odoo ERP.

المُدخل: صف من إطار APQC PCF Cross-Industry يحتوي:
- PCF ID
- Hierarchy ID (مثل 4.1.2)
- Name (اسم العملية)

المطلوب: صنّف العملية وأخرِج JSON بالحقول التالية:

{
  "pcf_id": "<المعرّف>",
  "hierarchy_id": "<الرقم الهرمي>",
  "name": "<الاسم>",
  "category_type": "operating | management_support",
  "activity_class": "primary | support",
  "value_model": "chain | shop | network | shared",
  "porter_activity": "<أحد: inbound_logistics | operations |
      outbound_logistics | marketing_sales | service |
      firm_infrastructure | hrm | technology_development | procurement>",
  "stabell_primary": "<إن كان أساسياً: للسلسلة (logistics/operations/...)،
      للمتجر (problem_finding/problem_solving/choice/execution/control)،
      للشبكة (network_promotion/service_provisioning/infrastructure)>",
  "odoo_modules": ["<وحدات Odoo المنفّذة>"],
  "odoo_models": ["<نماذج ir.model ذات الصلة>"],
  "rationale": "<سبب التصنيف في جملة>"
}

قواعد التصنيف:
1. الفئات 1.0–6.0 = operating؛ والفئات 7.0–13.0 = management_support.
2. فئة 4.0 (Deliver Physical Products) → value_model=chain.
   فئة 5.0 (Deliver Services) → value_model=shop.
   فئات 6.0/12.0 (خدمة العملاء/العلاقات) → value_model=network.
   فئات 1.0–3.0 → value_model=shared (تخدم النماذج الثلاثة).
3. الفئات 7.0–13.0 → activity_class=support، وحدّد porter_activity
   المناسب (HR→hrm، IT/13.0→technology_development، 9.0/10.0/11.0→
   firm_infrastructure، 12.0→procurement/external).
4. اربط بوحدات Odoo الفعلية (purchase/mrp/stock/sale/project/
   hr_timesheet/website/payment/account/hr/approvals…).
5. إن كانت العملية تمكينية عامة (استراتيجية/مالية) ولا تَخلق القيمة
   مباشرة، اجعل activity_class=support حتى لو كانت في عمليات تشغيلية.

أخرِج JSON فقط دون شرح إضافي.
```

### مثال على استخدام البرومبت
**المدخل:** `10215 | 4.1 | Plan for and align supply chain resources`
**المخرج المتوقّع:**
```json
{
  "pcf_id": "10215", "hierarchy_id": "4.1",
  "name": "Plan for and align supply chain resources",
  "category_type": "operating", "activity_class": "primary",
  "value_model": "chain",
  "porter_activity": "inbound_logistics",
  "stabell_primary": "inbound_logistics",
  "odoo_modules": ["purchase", "stock", "mrp"],
  "odoo_models": ["purchase.order", "stock.warehouse.orderpoint", "mrp.production"],
  "rationale": "تخطيط موارد سلسلة التوريد نشاط أساسي تحويلي في نموذج السلسلة."
}
```

> يمكن تشغيل البرومبت على كل صفوف الإكسل (آلاف العمليات) لإنتاج **جدول ربط شامل**
> APQC↔القيمة↔Odoo قابل للاستيراد كبيانات `value.activity` (انظر
> `VALUE_CONFIGURATION_METHODOLOGY.md §4`).

---

## 5. سير العمل: من الإكسل إلى نموذج قيمة قابل للقياس

```
ملف APQC PCF (الإكسل)
   │  ① قراءة الصفوف (openpyxl): PCF ID, Hierarchy ID, Name
   ▼
تشغيل البرومبت (§4) على كل صف
   │  ② تصنيف: operating/support → primary/support → chain/shop/network → Odoo
   ▼
جدول ربط شامل (JSON/CSV)
   │  ③ استيراد إلى value.configuration / value.activity
   ▼
نموذج قيمة حيّ في Odoo
   │  ④ ربط كل نشاط بـ ir.model + base.automation (ARIS/BPMN)
   ▼
قياس المحرّكات من بيانات Odoo الحيّة (تكلفة/إيراد عبر المحاسبة التحليلية)
```

---

## 6. الخلاصة

- **الإكسل = إطار APQC PCF**: 13 فئة في هرم (فئة→مجموعة→عملية→نشاط)، مقسومة أصلاً إلى
  **تشغيلية (1.0–6.0)** و**داعمة (7.0–13.0)** — مطابِقة لتمييز الأساسية/الداعمة.
- **الربط الجوهري:** فئة التسليم في APQC تحدّد النموذج —
  **4.0→السلسلة، 5.0→المتجر، 6.0/12.0→الشبكة**؛ والفئات 1.0–3.0 مشتركة؛ و7.0–13.0 داعمة.
- **البرومبت الجاهز (§4)** يصنّف أي صف من الإكسل آلياً إلى
  (تشغيلي/داعم → أساسي/داعم → نموذج → نشاط Porter/Stabell → وحدات ونماذج Odoo) بصيغة JSON.
- **سير العمل** يحوّل الإكسل إلى **نموذج قيمة حيّ وقابل للقياس** في Odoo عبر استيراده كـ
  `value.activity` وربطه بالمحاسبة التحليلية.

باختصار: إطار APQC في الإكسل يوفّر **القائمة المعيارية لكل عمليات المنشأة**، ونماذج القيمة
الثلاثة توفّر **منطق التصنيف**، وOdoo يوفّر **التنفيذ والقياس** — والبرومبت هو الجسر الذي
يربط الثلاثة آلياً.

---

*المصادر: ملف APQC PCF Cross-Industry v7.2.1 vs v6.1.1 (13 فئة، أوراق 1.0–13.0)؛ نماذج
القيمة (Stabell & Fjeldstad 1998)؛ وحدات Odoo. مكمّلة لـ `VALUE_MODELS_THREE_AR.md`,
`PRIMARY_ACTIVITIES_AR.md`, `SUPPORT_ACTIVITIES_AR.md`,
`PRIMARY_SUPPORT_INTEGRATION_AR.md`, `VALUE_CONFIGURATION_METHODOLOGY.md`. Odoo 19.0.*
