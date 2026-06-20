#!/usr/bin/env python3
"""Heuristic auto-classifier: derive (value_model, activity_class, apqc) for a
module from its facts (category, name, depends). Used by the mass sweep to give
every remaining module a baseline record. Deep agent review overrides these.

Confidence is intentionally low — these are inferred-from-category guesses,
flagged as such in the generated record's open_questions.
"""
from __future__ import annotations

# (value_model, activity_class, apqc) by name-prefix / substring — most specific first
NAME_RULES = [
    ("l10n_",        ("support", "support", "9.0 Manage Financial Resources")),
    ("account",      ("support", "support", "9.0 Manage Financial Resources")),
    ("payment",      ("network", "support", "9.0 Manage Financial Resources")),
    ("pos_",         ("chain",   "primary", "3.0 Market and Sell Products and Services")),
    ("point_of_sale",("chain",   "primary", "3.0 Market and Sell Products and Services")),
    ("mrp",          ("chain",   "primary", "4.3 Produce/Manufacture/Deliver Product")),
    ("stock",        ("chain",   "support", "4.0 Deliver Physical Products")),
    ("delivery",     ("chain",   "support", "4.4 Operate outbound transportation")),
    ("purchase",     ("support", "support", "4.2 Procure Materials and Services")),
    ("sale_subscription", ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("sale",         ("chain",   "primary", "3.0 Market and Sell Products and Services")),
    ("crm",          ("shop",    "primary", "3.0 Market and Sell Products and Services")),
    ("hr_recruit",   ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("hr_payroll",   ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("hr_",          ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("hr",           ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("project",      ("shop",    "primary", "5.0 Deliver Services")),
    ("timesheet",    ("shop",    "primary", "5.0 Deliver Services")),
    ("helpdesk",     ("shop",    "primary", "6.0 Manage Customer Service")),
    ("website_sale", ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("website_event",("network", "primary", "3.0 Market and Sell Products and Services")),
    ("website",      ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("theme_",       ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("mass_mailing", ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("marketing",    ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("social",       ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("event",        ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("sms",          ("support", "support", "9.4 Manage internal communications")),
    ("mail",         ("support", "support", "9.4 Manage internal communications")),
    ("im_livechat",  ("network", "primary", "6.0 Manage Customer Service")),
    ("calendar",     ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("fleet",        ("support", "support", "10.0 Acquire, Construct, and Manage Assets")),
    ("maintenance",  ("support", "support", "10.0 Acquire, Construct, and Manage Assets")),
    ("repair",       ("chain",   "support", "4.0 Deliver Physical Products")),
    ("loyalty",      ("support", "support", "3.0 Market and Sell Products and Services")),
    ("survey",       ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("sign",         ("support", "support", "11.0 Manage Enterprise Risk and Compliance")),
    ("documents",    ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("knowledge",    ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("spreadsheet",  ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("base_",        ("support", "support", "8.0 Manage Information Technology")),
    ("web",          ("support", "support", "8.0 Manage Information Technology")),
    ("iap",          ("support", "support", "8.0 Manage Information Technology")),
    ("auth_",        ("support", "support", "8.0 Manage Information Technology")),
    ("portal",       ("network", "support", "6.0 Manage Customer Service")),
    ("product",      ("support", "support", "2.0 Develop and Manage Products and Services")),
    ("uom",          ("support", "support", "2.0 Develop and Manage Products and Services")),
    ("contacts",     ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("phone",        ("support", "support", "8.0 Manage Information Technology")),
    ("digest",       ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("utm",          ("support", "support", "3.0 Market and Sell Products and Services")),
    ("link_tracker", ("support", "support", "3.0 Market and Sell Products and Services")),
    ("rating",       ("support", "support", "6.0 Manage Customer Service")),
    ("gamification", ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("resource",     ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("lunch",        ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("barcode",      ("chain",   "support", "4.0 Deliver Physical Products")),
    ("bus",          ("support", "support", "8.0 Manage Information Technology")),
    ("snailmail",    ("support", "support", "9.4 Manage internal communications")),
]

# category-keyword fallback (when name rules don't match)
CATEGORY_RULES = [
    ("accounting",   ("support", "support", "9.0 Manage Financial Resources")),
    ("point of sale",("chain",   "primary", "3.0 Market and Sell Products and Services")),
    ("sales",        ("chain",   "primary", "3.0 Market and Sell Products and Services")),
    ("subscription", ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("inventory",    ("chain",   "support", "4.0 Deliver Physical Products")),
    ("supply chain", ("chain",   "support", "4.0 Deliver Physical Products")),
    ("purchase",     ("support", "support", "4.2 Procure Materials and Services")),
    ("manufactur",   ("chain",   "primary", "4.3 Produce/Manufacture/Deliver Product")),
    ("human resour", ("support", "support", "7.0 Develop and Manage Human Capital")),
    ("website",      ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("marketing",    ("network", "primary", "3.0 Market and Sell Products and Services")),
    ("productivity", ("support", "support", "13.0 Develop and Manage Business Capabilities")),
    ("discuss",      ("support", "support", "9.4 Manage internal communications")),
    ("project",      ("shop",    "primary", "5.0 Deliver Services")),
    ("services",     ("shop",    "primary", "5.0 Deliver Services")),
    ("localization", ("support", "support", "9.0 Manage Financial Resources")),
]

DEFAULT = ("support", "support", "13.0 Develop and Manage Business Capabilities")


def classify(facts: dict) -> tuple[str, str, str]:
    name = (facts.get("module") or "").lower()
    cat = ((facts.get("manifest") or {}).get("category") or "").lower()
    for prefix, res in NAME_RULES:
        if name == prefix or name.startswith(prefix):
            return res
    for kw, res in CATEGORY_RULES:
        if kw in cat:
            return res
    return DEFAULT


if __name__ == "__main__":
    import json, sys
    print(classify(json.load(open(sys.argv[1]))))
