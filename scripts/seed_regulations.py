"""
Seed the regulations table with FATF, FinCEN, FINTRAC, and SR 11-7 excerpts.
Run once after applying schema.sql:
    python scripts/seed_regulations.py
"""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.db import get_conn
from src.retrieval import embed

REGULATIONS = [
    # ── FinCEN ──────────────────────────────────────────────────────────────
    {
        "source": "FinCEN",
        "section": "31 CFR 1010.311 — Currency Transaction Report (CTR) Threshold",
        "content": (
            "Each financial institution shall file a report of each deposit, withdrawal, exchange "
            "of currency or other payment or transfer, by, through, or to such financial institution "
            "which involves a transaction in currency of more than $10,000. Structuring transactions "
            "to evade the CTR filing requirement is a federal crime under 31 U.S.C. § 5324. "
            "Structuring includes breaking a transaction into smaller amounts (often just under $10,000) "
            "conducted on the same day or over multiple days, at one or more branches, and by one or "
            "more individuals acting in concert. Financial institutions must file a Suspicious Activity "
            "Report (SAR) when they know, suspect, or have reason to suspect structuring activity, "
            "regardless of the dollar amount involved."
        ),
    },
    {
        "source": "FinCEN",
        "section": "31 CFR 1020.320 — SAR Filing Obligation (Banks)",
        "content": (
            "A bank shall file a SAR with respect to a transaction conducted or attempted by, at, or "
            "through the bank and involving or aggregating $5,000 or more in funds or other assets "
            "where the bank knows, suspects, or has reason to suspect that: (i) the transaction "
            "involves funds derived from illegal activity or is intended to evade reporting "
            "requirements; (ii) the transaction is designed to evade BSA requirements; or (iii) "
            "the transaction has no lawful purpose or is not the sort in which the customer would "
            "normally be expected to engage. SARs must be filed within 30 days of detection. "
            "The filing institution must retain a copy of the SAR and supporting documentation "
            "for five years."
        ),
    },
    {
        "source": "FinCEN",
        "section": "FIN-2010-A001 — Guidance on Identifying Structuring Activity",
        "content": (
            "FinCEN advisory: structuring red flags include: multiple cash transactions just below "
            "the $10,000 reporting threshold on the same day or consecutive days; use of multiple "
            "bank branches or tellers; transactions involving two or more individuals who appear to "
            "be acting together; customer requests for information about reporting thresholds; "
            "customer nervousness when approached by staff; splitting deposits between multiple "
            "accounts for the same beneficial owner. Financial institutions should consider the "
            "totality of circumstances — a single below-threshold deposit is not structuring; "
            "a pattern of deposits just under $10,000 across multiple dates and branches is."
        ),
    },
    {
        "source": "FinCEN",
        "section": "FIN-2014-A005 — Trade-Based Money Laundering (TBML) Advisory",
        "content": (
            "TBML involves the movement of value through trade transactions to disguise money "
            "laundering. Red flags include: over- or under-invoicing of goods and services; "
            "multiple invoicing for the same shipment; falsely described goods or services; "
            "shipments to or from high-risk jurisdictions inconsistent with customer's business; "
            "third-party payments where the payer has no apparent connection to the trade; "
            "payments settled in cash or via informal value transfer systems; "
            "significant discrepancies between declared value and market value of goods; "
            "transactions involving shell or front companies with no apparent business substance. "
            "Financial institutions should file a SAR when TBML indicators are present and "
            "cannot be reasonably explained."
        ),
    },
    {
        "source": "FinCEN",
        "section": "FIN-2006-G015 — Guidance on Round-Trip / Rapid Movement Transactions",
        "content": (
            "Round-tripping involves transferring funds out of the financial system and back in "
            "a manner designed to disguise the origin of the funds. Indicators include: funds "
            "wired to an offshore account and returned to the same or related account within "
            "days or weeks; wire transfers to high-risk offshore jurisdictions with immediate "
            "return wires; absence of commercial rationale for the transfers; minimal price "
            "change between outgoing and incoming amounts, suggesting no genuine investment or "
            "trade; use of correspondent banking chains to obscure beneficial ownership. "
            "Rapid movement between accounts — also known as 'layering' — is a core ML typology "
            "and is sufficient basis for a SAR when corroborated by customer profile anomalies."
        ),
    },
    # ── FATF ────────────────────────────────────────────────────────────────
    {
        "source": "FATF",
        "section": "Recommendation 3 — Money Laundering Offence",
        "content": (
            "Countries should criminalise money laundering on the basis of the Vienna Convention "
            "and the Palermo Convention. Countries should apply the crime of money laundering to "
            "all serious offences, with a view to including the widest range of predicate offences. "
            "The three stages of money laundering are: placement (introducing illicit funds into "
            "the financial system); layering (disguising the audit trail through a series of "
            "complex transactions); and integration (reintroducing laundered funds into the "
            "legitimate economy). Financial institutions must identify, assess, and mitigate ML/TF "
            "risks at onboarding and on an ongoing basis."
        ),
    },
    {
        "source": "FATF",
        "section": "Recommendation 10 — Customer Due Diligence",
        "content": (
            "Financial institutions are prohibited from keeping anonymous accounts or accounts in "
            "obviously fictitious names. Institutions must apply Customer Due Diligence (CDD) "
            "measures when: establishing a business relationship; carrying out occasional "
            "transactions above USD/EUR 15,000; there is suspicion of ML/TF; or doubts exist about "
            "the veracity of previously obtained customer identification data. Enhanced Due Diligence "
            "(EDD) is required for higher-risk customers including Politically Exposed Persons (PEPs), "
            "customers from high-risk jurisdictions, and customers with complex or unusual ownership "
            "structures including nominee shareholders and bearer shares."
        ),
    },
    {
        "source": "FATF",
        "section": "Recommendation 14 — Money or Value Transfer Services",
        "content": (
            "Countries should take measures to ensure that natural or legal persons that provide "
            "money or value transfer services (MVTS) — including hawala and other informal value "
            "transfer systems — are licensed or registered and subject to effective AML/CFT measures. "
            "TBML through MVTS involves the use of trade invoices and documentation to disguise "
            "the movement of value across borders. Over-invoicing, under-invoicing, and phantom "
            "shipments are the primary TBML mechanisms. Financial institutions facilitating "
            "international wire transfers must monitor for inconsistencies between declared trade "
            "values and market prices and file STRs when material discrepancies are identified."
        ),
    },
    {
        "source": "FATF",
        "section": "Recommendation 24 — Transparency and Beneficial Ownership of Legal Persons",
        "content": (
            "Countries must prevent the misuse of legal persons for ML/TF by ensuring adequate, "
            "accurate, and timely information on the beneficial ownership and control of legal "
            "persons is obtainable by competent authorities. Beneficial ownership — the natural "
            "person(s) who ultimately own or control a customer — must be identified when it "
            "reaches 25% or more ownership interest, or through control via other means. "
            "Shell companies with no apparent business purpose, nominee directors, complex "
            "multi-jurisdictional ownership chains, and registered agents in secrecy havens "
            "(British Virgin Islands, Cayman Islands, Panama, Marshall Islands, Delaware) are "
            "red flags indicating potential misuse for layering illicit funds. Financial "
            "institutions must file a SAR when beneficial ownership cannot be determined and "
            "the transaction pattern is consistent with layering."
        ),
    },
    {
        "source": "FATF",
        "section": "Recommendation 20 — Reporting of Suspicious Transactions",
        "content": (
            "If a financial institution suspects or has reasonable grounds to suspect that funds "
            "are the proceeds of a criminal activity, or are related to terrorist financing, it "
            "should be required, directly by law or regulation, to report promptly its suspicions "
            "to the financial intelligence unit (FIU). The obligation to report applies regardless "
            "of the dollar amount involved. The threshold for reporting is reasonable suspicion — "
            "a lower standard than probable cause or balance of probabilities. Institutions are "
            "protected from criminal and civil liability for good-faith SAR filings (tipping-off "
            "prohibitions apply: do not disclose the SAR or its contents to the subject)."
        ),
    },
    # ── FINTRAC ─────────────────────────────────────────────────────────────
    {
        "source": "FINTRAC",
        "section": "PCMLTFA s.7 — Suspicious Transaction Report (STR) Obligation",
        "content": (
            "Every reporting entity that has reasonable grounds to suspect that a transaction or "
            "attempted transaction is related to the commission of a money laundering offence or "
            "terrorist activity financing offence must report the transaction to FINTRAC as soon "
            "as practicable and in any case within 30 days after the day on which the measures "
            "taken to establish reasonable grounds were completed. Reasonable grounds is a lower "
            "standard than on the balance of probabilities. There is no monetary threshold for "
            "STR filing — the obligation is triggered by suspicion alone. An STR must not be "
            "disclosed to the subject of the report (tipping-off prohibition under PCMLTFA s.8)."
        ),
    },
    {
        "source": "FINTRAC",
        "section": "PCMLTFA — Large Cash Transaction Report (LCTR) $10,000 Threshold",
        "content": (
            "Every reporting entity must submit a Large Cash Transaction Report (LCTR) to FINTRAC "
            "within 15 days of receiving $10,000 or more in cash in a single transaction or in "
            "two or more cash transactions totalling $10,000 or more within 24 consecutive hours "
            "if the entity knows, suspects, or should know the transactions were conducted by or "
            "on behalf of the same individual or entity. Structuring transactions to avoid the "
            "$10,000 LCTR threshold is an offence under the PCMLTFA. Structuring indicators "
            "include: multiple deposits just under $10,000 across branches; customer inquiries "
            "about reporting thresholds; use of multiple individuals to deposit cash on behalf "
            "of one beneficial owner."
        ),
    },
    {
        "source": "FINTRAC",
        "section": "FINTRAC Guideline 2 — Suspicious Transactions — Shell Company Red Flags",
        "content": (
            "FINTRAC guidance identifies the following shell company and layering red flags: "
            "a company with no apparent business purpose or employees; a company registered in "
            "a secrecy jurisdiction (BVI, Cayman, Panama, etc.) with transactions disproportionate "
            "to its stated activity; wire transfers to or from jurisdictions with weak AML "
            "frameworks on the FATF grey list or blacklist; multiple layers of corporate ownership "
            "with no identifiable natural-person beneficial owner; intercompany loans or payments "
            "with no supporting documentation; accounts opened by a nominee director or legal agent "
            "on behalf of an undisclosed principal. These factors, alone or in combination, may "
            "constitute reasonable grounds to suspect ML and trigger an STR obligation."
        ),
    },
    # ── SR 11-7 ─────────────────────────────────────────────────────────────
    {
        "source": "Federal Reserve SR 11-7",
        "section": "Supervisory Guidance on Model Risk Management — Governance",
        "content": (
            "SR 11-7 establishes supervisory expectations for model risk management at banking "
            "organizations. Models used in BSA/AML compliance (transaction monitoring systems, "
            "risk scoring engines, AI triage tools) are subject to model risk management "
            "requirements including: (1) model development documentation with clear assumptions "
            "and limitations; (2) independent model validation by a party separate from development; "
            "(3) ongoing monitoring of model performance and output distributions; (4) board and "
            "senior management oversight with defined model risk appetite. AI-assisted triage "
            "tools that recommend SAR filings or risk tier classifications are models under SR 11-7 "
            "and require an auditable decision trail — every output must be traceable to its "
            "inputs, retrieval context, and reasoning steps. Human analyst review of AI recommendations "
            "is required before any regulatory action."
        ),
    },
    {
        "source": "Federal Reserve SR 11-7",
        "section": "Supervisory Guidance on Model Risk Management — Audit Trail",
        "content": (
            "SR 11-7 requires that model outputs be reproducible and auditable. For AI/ML models "
            "used in compliance decisions: all input data, retrieved context, model outputs, and "
            "the analyst's final disposition must be logged with sufficient detail for an examiner "
            "to reconstruct the decision. Hash-chaining or cryptographic binding of log entries "
            "to prevent post-hoc modification is a best practice. Where a model uses retrieval-"
            "augmented generation (RAG), the specific retrieved passages and their source citations "
            "must be logged alongside the model output. The analyst's override or acceptance of "
            "the model recommendation must also be recorded. Retention period: five years minimum, "
            "consistent with BSA recordkeeping requirements under 31 CFR 1010.430."
        ),
    },
]


def seed(conn) -> None:
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM regulations")
        count = cur.fetchone()[0]
        if count > 0:
            print(f"Regulations table already has {count} rows — skipping seed.")
            return

    print(f"Embedding and inserting {len(REGULATIONS)} regulation chunks...")
    with conn.cursor() as cur:
        for i, reg in enumerate(REGULATIONS, 1):
            vec = embed(reg["content"])
            cur.execute(
                "INSERT INTO regulations (source, section, content, embedding) VALUES (%s, %s, %s, %s::vector)",
                (reg["source"], reg["section"], reg["content"], vec),
            )
            print(f"  [{i}/{len(REGULATIONS)}] {reg['source']} — {reg['section'][:60]}")
    conn.commit()
    print("Done. Regulations seeded successfully.")


if __name__ == "__main__":
    conn = get_conn()
    try:
        seed(conn)
    finally:
        conn.close()
