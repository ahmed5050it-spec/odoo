# ما الذي يمكن عكسه (Reverse-Engineer) من كود Odoo؟
# مقابل ميتاموديل «مواءمة معمارية الأعمال وتقنية المعلومات»

> الملف المرفوع `business_it_architecture_ali.pdf` هو ورقة **Business Architecture Guild**
> (سبتمبر 2025): «مواءمة معمارية الأعمال وتقنية المعلومات في ميتاموديل مشترك». يعرّف
> عناصر **معمارية الأعمال** (القدرات، تدفّقات القيمة، المفاهيم المعلوماتية، التنظيم،
> الاستراتيجية، المتطلّبات) وعناصر **معمارية تقنية المعلومات** (التطبيق/الخدمة/الميزة،
> البيانات/البيانات المنطقية/مخزن البيانات).
>
> سؤالك: **ما الذي يمكن عَكْسُه من الكود؟** — أي أيّ عناصر هذا الميتاموديل يستطيع
> **محرّك revres** (`doc/revres/extract_module.py`) و**ميتاداتا Odoo** استخراجها آلياً،
> وأيّها يحتاج معرفة بشرية. الجواب أدناه. مكمّلة لـ `REVRES_WORKFLOW.md`،
> `ARIS_METHODOLOGY.md`، ووثائق القيمة.

---

## 1. القاعدة: نصفان مختلفان في قابلية العكس

```
   معمارية تقنية المعلومات (IT Arch)          معمارية الأعمال (Business Arch)
   ───────────────────────────────           ──────────────────────────────
   مُشفّرة في الكود ⟹ قابلة للعكس ✅          نيّة بشرية ⟹ غير مُشفّرة غالباً
   (تطبيقات، خدمات، نماذج بيانات)             (استراتيجية، متطلّبات، قدرات)

   ✅ نعم آلياً     ◐ جزئياً (تلميح من الكود)     ✗ لا (يحتاج إنساناً)
```

**الخلاصة المبكرة:** نصف **IT Architecture** (التطبيق + البيانات) **قابل للعكس آلياً
بالكامل تقريباً** من كود Odoo. نصف **Business Architecture** **قابل للاستنتاج جزئياً**
(القدرات وتدفّقات القيمة من بنية الموديولات + تصنيف نماذج القيمة)، لكن **الاستراتيجية
والمتطلّبات لا تُعكَس** — فهي نيّة بشرية ليست في الكود.

---

## 2. الجدول الكامل: عنصر الميتاموديل ↔ هل يُعكَس من Odoo؟

| عنصر الميتاموديل | الطبقة | يُعكَس؟ | كيف من كود Odoo | أداة revres |
|------------------|--------|:------:|------------------|-------------|
| **Application** (تطبيق) | IT/App | ✅ | كل **module** = تطبيق؛ `__manifest__.py` | `extract_module.py` → manifest |
| **Software Service** (خدمة) | IT/App | ✅ | مسارات الـ controllers (`@route`) = خدمات RPC/HTTP | `routes[]` (path/auth/type) |
| **Software Feature** (ميزة) | IT/App | ◐ | الإجراءات (`ir.actions`)، القوائم، دوال النموذج | عدّ الـ views/methods |
| **Application/Information Flow** (تدفّق) | IT/App | ◐ | رسم الاعتماديات (`depends`) + العلاقات بين النماذج + `base.automation` | `depends` + `relation` في facts |
| **Data / Data Object** (بيانات) | IT/Data | ✅ | `ir.model` (الكيانات) | `models[]._name` |
| **Logical Data** (بيانات منطقية) | IT/Data | ✅ | `ir.model.fields` + العلاقات (m2o/o2m/m2m) = ERM | `fields{}` + `relation` |
| **Data Store** (مخزن) | IT/Data | ✅ | جداول PostgreSQL، `_table`، طبقات التقييم | (تشغيل عبر run-odoo) |
| **Information Concept** (مفهوم معلوماتي) | Business | ✅ | الكائنات التجارية: `res.partner`, `product.template`, `account.move` | `models[]` ذات `_name` |
| **Organization** (تنظيم) | Business | ✅ | `res.company` / `res.groups` / `res.users` | `security` + موديول `base` |
| **Product** (منتج) | Business | ✅ | `product.template` (+ السمات/المتغيّرات) | facts لموديول `product` |
| **Capability** (قدرة) | Business | ◐ | تُستنتَج من فئة الموديول ونماذجه (تصنيف revres) | حقل `category` + التصنيف |
| **Capability Instance/Behavior** | Business | ◐ | دوال النموذج، `ir.actions.server`، الأتمتة | عدّ methods + routes |
| **Value Stream** (تدفّق قيمة) | Business | ◐ | تسلسل المستندات (sale→stock→account) + سلاسل `base.automation` | `depends` graph + نماذج القيمة |
| **Stakeholder** (صاحب مصلحة) | Business | ◐ | `res.partner` + المتابعون (`mail.followers`) | facts لـ `mail`/`base` |
| **Requirement** (متطلّب) | جسر | ✗ | غير موجود في الكود (وثائق/تذاكر بشرية) | — |
| **Strategy** (استراتيجية) | Business | ✗ | نيّة بشرية، غير مُشفّرة | — |

رموز: ✅ يُعكَس آلياً · ◐ يُستنتَج جزئياً (تلميح من الكود يحتاج تأكيداً) · ✗ لا يُعكَس.

---

## 3. الطبقات الثلاث وقابلية عكسها

### ٣.١ معمارية البيانات (Data Architecture) — **الأعلى قابليةً للعكس ✅**
الورقة تعرّف: Data → Logical Data → Data Store. في Odoo هذه **بالضبط** هي ميتاموديل ORM:
- **Data Object** = `ir.model` (الكيان).
- **Logical Data** = `ir.model.fields` + العلاقات = نموذج الكيان-العلاقة (ERM).
- **Data Store** = جدول PostgreSQL.

محرّك revres يستخرجها مباشرةً (انظر `ARIS_METHODOLOGY.md §3.2`): «استعلام ميتاداتا، لا
رسم يدوي».

### ٣.٢ معمارية التطبيقات (Application Architecture) — **قابلة للعكس ✅/◐**
الورقة: Application → Software Service → Software Feature.
- **Application** = الموديول (manifest) ✅.
- **Software Service** = مسار `@route` (واجهة RPC/HTTP) ✅ — facts تستخرج المسارات.
- **Software Feature** = إجراء/قائمة/دالة ◐ — تُعدّ لكن «الميزة» مفهوم أدقّ من العدّ.
- **Information Flow** = رسم الاعتماديات + العلاقات + أحداث `base.automation` ◐.

### ٣.٣ معمارية الأعمال (Business Architecture) — **جزئية ◐ إلى ✗**
- **Information Concept / Organization / Product** = كائنات Odoo فعلية ✅
  (`res.partner`, `res.groups`, `product.template`).
- **Capability / Value Stream** = تُستنتَج من بنية الموديولات وتصنيف نماذج القيمة
  (chain/shop/network) ◐ — تلميح قوي لكنه ليس تصريحاً صريحاً في الكود.
- **Strategy / Requirements** = ✗ لا تُعكَس؛ نيّة وقرارات بشرية خارج الكود.

---

## 4. لماذا «جزئي» لمعمارية الأعمال؟ (الفجوة الجوهرية)

```
   الكود يقول:   "ما الذي بُني وكيف يترابط"   (البنية = حقيقة)
   الأعمال تقول:  "لماذا بُني ولأيّ هدف"        (النيّة = قرار بشري)

   ⟹ revres يعكس البنية (IT Arch) بدقّة،
      ويُلمّح للأعمال (Capability/Value Stream) عبر التصنيف،
      لكنه لا يخترع الاستراتيجية أو المتطلّبات.
```

مثال: من الكود نعرف أن `sale.order` يعتمد على `account` ويولّد `stock.picking` — هذه
**تدفّق تطبيقي مُعكوس بدقّة**. لكن «هل هذا تدفّق القيمة *الاستراتيجي* للشركة؟» قرار يحتاج
إنساناً يربطه بالاستراتيجية.

---

## 5. كيف يملأ محرّك revres الجدول عملياً

| ناتج revres | يغطّي عنصر الميتاموديل |
|-------------|------------------------|
| `manifest` (name/category/depends) | Application + تلميح Capability |
| `models[]._name/_description` | Data Object + Information Concept |
| `fields{}` + `relation` | Logical Data (ERM) + Information Flow |
| `routes[]` | Software Service |
| `views` + methods | Software Feature (تقريبي) |
| `security` (groups/rules) | Organization |
| تصنيف نماذج القيمة + APQC | Capability + Value Stream (استنتاج) |
| تشغيل `run-odoo` (DB حيّة) | Data Store + تأكيد التدفّقات وقت التشغيل |

أي أن **مخرجات `extract_module.py` + تصنيف `PROMPT.md`** تبني **نصف IT Architecture
بالكامل ونصف Business Architecture استنتاجاً** — تماماً ما يطلبه ميتاموديل المواءمة، عدا
الاستراتيجية/المتطلّبات.

---

## 6. الخلاصة — جواب «ما الذي يمكن عكسه من الكود؟»

- ✅ **يُعكَس آلياً بالكامل (من الكود/الميتاداتا):**
  معمارية **البيانات** كلها (Data Object, Logical Data/ERM, Data Store)، ومعظم معمارية
  **التطبيقات** (Application, Software Service)، والكائنات التجارية والتنظيم
  (Information Concept, Organization, Product). هذه هي قوّة محرّك revres.
- ◐ **يُستنتَج جزئياً (تلميح من الكود + تأكيد بشري):**
  **Capability، Value Stream، Software Feature، Information Flow، Stakeholder** — عبر
  بنية الموديولات + تصنيف نماذج القيمة (chain/shop/network) + APQC.
- ✗ **لا يُعكَس من الكود (نيّة بشرية):**
  **Strategy و Requirements** — قرارات وأهداف ليست مُشفّرة في أي سطر كود.

القاعدة الذهبية: **الكود يكشف «ما» و«كيف» (طبقة IT بدقّة، وطبقة الأعمال البنيوية
استنتاجاً)، لكنه لا يكشف «لماذا» (الاستراتيجية والمتطلّبات)**. لذلك يعكس revres الجانب
التقني من ميتاموديل المواءمة بالكامل، ويترك الجانب الاستراتيجي للإنسان — وهذا بالضبط
الحدّ الفاصل بين الهندسة العكسية والقرار المعماري.

---

*المصادر: ورقة Business Architecture Guild «Business and IT Architecture Metamodel
Alignment» (سبتمبر 2025)؛ محرّك `doc/revres/extract_module.py` ووثيقة
`REVRES_WORKFLOW.md`؛ `ARIS_METHODOLOGY.md`؛ نماذج القيمة و`APQC_PCF_VALUE_MODELS_AR.md`.
Odoo 19.0.*
