"""Regulatory knowledge base ingestion and legal chunking pipeline."""

import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

from langchain_core.documents import Document

from backend.core.config import settings
from backend.rag.hybrid_retriever import hybrid_retriever
from backend.rag.vector_store import vector_store_manager

logger = logging.getLogger(__name__)

# Canonical statutory text seeds covering EU AI Act, BaFin BDAI, MaRisk, KWG, and WpHG
SEED_REGULATORY_CORPUS = [
    # -------------------------------------------------------------
    # EU AI ACT (Regulation (EU) 2024/1689) - English
    # -------------------------------------------------------------
    {
        "category": "eu_ai_act",
        "filename": "eu_ai_act_prohibited_practices.txt",
        "language": "en",
        "source_document": "EU AI Act (Regulation (EU) 2024/1689)",
        "article_section_id": "Article 5",
        "content": """Article 5: Prohibited Artificial Intelligence Practices
1. The following artificial intelligence practices shall be prohibited:
(a) the placing on the market, the putting into service or the use of an AI system that deploys subliminal techniques beyond a person's consciousness or purposefully manipulative or deceptive techniques, with the objective, or the effect of materially distorting the behaviour of a person or a group of persons by appreciably impairing their ability to make an informed decision;
(b) the placing on the market, the putting into service or the use of an AI system that exploits any of the vulnerabilities of a natural person or a specific group of persons due to their age, disability or a specific social or economic situation;
(c) the placing on the market, the putting into service or the use of AI systems for the evaluation or classification of natural persons or groups of persons over a certain period of time based on their social behaviour or known, inferred or predicted personal or personality characteristics, with the social score leading to either:
(i) detrimental or unfavourable treatment of certain natural persons or groups of persons in social contexts that are unrelated to the contexts in which the data was originally generated or collected;
(ii) detrimental or unfavourable treatment of certain natural persons or groups of persons that is unjustified or disproportionate to their social behaviour or its gravity;
(d) the placing on the market, the putting into service or the use of AI systems for making risk assessments of natural persons in order to assess or predict the likelihood of a natural person committing a criminal offence based solely on profiling;
(e) the placing on the market, the putting into service or the use of 'real-time' remote biometric identification systems in publicly accessible spaces for the purpose of law enforcement, unless strictly necessary for specific narrow exceptions."""
    },
    {
        "category": "eu_ai_act",
        "filename": "eu_ai_act_high_risk_classification.txt",
        "language": "en",
        "source_document": "EU AI Act (Regulation (EU) 2024/1689)",
        "article_section_id": "Article 6 & Annex III Point 5(b)",
        "content": """Article 6: Classification rules for high-risk AI systems
1. Irrespective of whether an AI system is placed on the market or put into service independently from products referred to in Annex I, that AI system shall be considered high-risk where both of the following conditions are fulfilled:
(a) the AI system is intended to be used as a safety component of a product, or the AI system is itself a product, covered by the Union harmonisation legislation listed in Annex I;
(b) the product whose safety component pursuant to point (a) is the AI system, or the AI system itself as a product, is required to undergo a third-party conformity assessment.
2. In addition to the high-risk AI systems referred to in paragraph 1, AI systems referred to in Annex III shall be considered high-risk.

ANNEX III: HIGH-RISK AI SYSTEMS REFERRED TO IN ARTICLE 6(2)
Point 5: Access to and enjoyment of essential private services and essential public services and benefits:
(a) AI systems intended to be used by public authorities or on behalf of public authorities to evaluate the eligibility of natural persons for public assistance benefits and services, as well as to grant, reduce, revoke, or reclaim such benefits and services;
(b) AI systems intended to be used to evaluate the creditworthiness of natural persons or establish their credit score, with the exception of AI systems used for the purpose of detecting financial fraud;
(c) AI systems intended to be used for risk assessment and pricing in relation to natural persons in the case of life and health insurance."""
    },
    {
        "category": "eu_ai_act",
        "filename": "eu_ai_act_high_risk_obligations.txt",
        "language": "en",
        "source_document": "EU AI Act (Regulation (EU) 2024/1689)",
        "article_section_id": "Articles 9, 10, 14",
        "content": """Article 9: Risk management system
1. A risk management system shall be established, implemented, documented and maintained in relation to high-risk AI systems.
2. The risk management system shall be understood as a continuous iterative process planned and run throughout the entire lifecycle of a high-risk AI system, requiring regular systematic review and updating.

Article 10: Data and data governance
1. High-risk AI systems which make use of techniques involving the training of models with data shall be developed on the basis of training, validation and testing data sets that meet the quality criteria referred to in paragraphs 2 to 5.
2. Training, validation and testing data sets shall be subject to appropriate data governance and management practices.

Article 14: Human oversight
1. High-risk AI systems shall be designed and developed in such a way, including with appropriate human-machine interface tools, that they can be effectively overseen by natural persons during the period in which they are in use.
4. For the purpose of implementing paragraphs 1, 2 and 3, high-risk AI systems shall be provided to the deployer in such a way that natural persons to whom human oversight is assigned are enabled to:
(a) properly understand the relevant capacities and limitations of the high-risk AI system and be able to duly monitor its operation;
(b) remain aware of the possible tendency of automatically relying or over-relying on the output produced by a high-risk AI system (automation bias);
(c) correctly interpret the high-risk AI system's output;
(d) decide, in any particular situation, not to use the high-risk AI system or otherwise disregard, override or reverse the output;
(e) intervene on the operation of the high-risk AI system or interrupt the system through a "stop" button or a similar procedure."""
    },

    # -------------------------------------------------------------
    # BAFIN BDAI PRINCIPLES (2021) - English
    # -------------------------------------------------------------
    {
        "category": "bafin",
        "filename": "bafin_bdai_principles_2021.txt",
        "language": "en",
        "source_document": "BaFin BDAI Principles (2021)",
        "article_section_id": "Principles 1 to 4",
        "content": """BaFin Principles for the Use of Algorithms in Decision-Making Processes (BDAI 2021)
Principle 1 (Clear Responsibilities): The management board bears overall responsibility for the use of algorithms in decision-making processes. Clear internal lines of responsibility and governance structures must be established.
Principle 2 (Appropriate Human Oversight): Processes that make critical decisions affecting bank customers or risk exposure must have meaningful human oversight and clear escalation mechanisms.
Principle 3 (Explainability and Traceability): Institutions must ensure an adequate level of explainability and traceability for algorithmic decisions. The rationale behind credit assessments and automated recommendations must be reconstructible by internal control functions and supervisors.
Principle 4 (Data Quality and Bias Prevention): High data quality standards must be maintained across training, testing, and production data. Unintended discrimination and biased statistical correlation must be systematically mitigated."""
    },

    # -------------------------------------------------------------
    # MARISK (Mindestanforderungen an das Risikomanagement) - AT 4.3.2 - German & English
    # -------------------------------------------------------------
    {
        "category": "bafin",
        "filename": "marisk_at_4_3_2_model_risk.txt",
        "language": "de",
        "source_document": "BaFin MaRisk (Rundschreiben 10/2021)",
        "article_section_id": "AT 4.3.2",
        "content": """MaRisk AT 4.3.2 Modellrisikomanagement (Tz. 1 - 3)
1. Die Institute müssen über angemessene Verfahren zur Identifizierung, Beurteilung, Steuerung sowie Überwachung und Kommunikation von Modellrisiken verfügen (Modellrisikomanagement). Dies gilt für alle quantitativen und qualitativen Modelle, insbesondere für Modelle zur Risikomessung, Kreditentscheidung, Preisgestaltung und Kapitalplanung.
2. Der Modelllebenszyklus umfasst die Modellinitiierung, -entwicklung, -validierung, -abnahme, -anwendung, -überwachung und -außerbetriebnahme. Jede Phase ist angemessen zu dokumentieren.
3. Vor dem ersten produktiven Einsatz sowie bei wesentlichen Modelländerungen ist eine unabhängige Modellvalidierung durchzuführen. Die Validierung umfasst die Prüfung der Modellkonzeption, der mathematisch-statistischen Verfahren, der Datenqualität und der Ergebnisgüte (einschließlich Backtesting und Sensitivitätsanalysen). Die Validierungseinheit muss organisatorisch von der Modellentwicklung unabhängig sein.
Hinweis: Diese Fassung gibt das rechtsverbindliche deutsche Original wieder."""
    },
    {
        "category": "bafin",
        "filename": "marisk_at_4_3_2_model_risk_en.txt",
        "language": "en",
        "source_document": "BaFin MaRisk Circular (AT 4.3.2 English Reference)",
        "article_section_id": "AT 4.3.2 (EN Translation)",
        "content": """BaFin MaRisk AT 4.3.2 Model Risk Management (Non-binding translation)
Disclaimer: This English version is provided for information purposes only. The original German text is binding in all respects.
1. Institutions must have appropriate processes for identifying, assessing, managing, monitoring, and communicating model risks (model risk management). This applies to all models used for risk measurement, credit decisions, pricing, and capital planning.
2. The model lifecycle encompasses model initiation, development, validation, approval, implementation, ongoing monitoring, and decommissioning. Each phase must be documented.
3. Prior to initial productive deployment and upon material changes, independent model validation must be performed, covering model conceptualization, statistical methodologies, data quality, backtesting, and sensitivity analysis."""
    },

    # -------------------------------------------------------------
    # BAFIN 2026 AI / ICT RISK GUIDANCE - German
    # -------------------------------------------------------------
    {
        "category": "bafin",
        "filename": "bafin_ai_ict_dora_2026.txt",
        "language": "de",
        "source_document": "BaFin Aufsichtliche Orientierungshilfe zu KI- und IKT-Risiken (Januar 2026)",
        "article_section_id": "Abschnitt 3: KI-Systeme und IKT-Sicherheitsanforderungen",
        "content": """BaFin Leitfaden zu KI- und IKT-Risiken unter Berücksichtigung von DORA (Januar 2026)
1. Der Einsatz von künstlicher Intelligenz in institutsinternen Prozessen unterliegt den allgemeinen Anforderungen an das Informations- und IKT-Risikomanagement nach DORA (Verordnung (EU) 2022/2554) sowie den MaRisk.
2. KI-Modelle, die von Drittanbietern bezogen oder in der Cloud betrieben werden, sind als wesentliche IKT-Dienstleistungen einzustufen. Die Institute haben sicherzustellen, dass ausreichende Einsichts- und Prüfungsrechte vereinbart sind.
3. Bei der Nutzung generativer KI-Modelle oder autonomer Agenten müssen technische Sicherheitsvorkehrungen gegen Prompt-Injection, Datenabfluss und Halluzinationen implementiert und regelmäßig auditiert werden.
4. Es ist ein Notfallkonzept bereitzuhalten, das den Ausfall oder die fehlerhafte Funktion des KI-Systems durch manuelle Rückfallprozesse auffängt."""
    },

    # -------------------------------------------------------------
    # STATUTES: KWG & WpHG - German
    # -------------------------------------------------------------
    {
        "category": "wphg_kwg",
        "filename": "kwg_paragraph_25a.txt",
        "language": "de",
        "source_document": "Kreditwesengesetz (KWG)",
        "article_section_id": "§ 25a KWG",
        "content": """§ 25a KWG: Besondere organisatorische Pflichten für Institute; Verordnungsermächtigung
(1) Ein Institut muss über eine ordnungsgemäße Geschäftsorganisation verfügen, die die Einhaltung der vom Institut zu beachtenden gesetzlichen Bestimmungen und der aufsichtsrechtlichen Vorgaben gewährleistet. Die Geschäftsorganisation muss insbesondere ein angemessenes und wirksames Risikomanagement umfassen, auf dessen Grundlage das Institut die wesentlichen Risiken laufend identifiziert, beurteilt, steuert, überwacht und kommuniziert.
Das Risikomanagement umfasst insbesondere:
1. eine Festlegung von Strategien (Geschäfts- und Risikostrategie),
2. Verfahren zur Ermittlung und Sicherstellung der Risikotragfähigkeit,
3. eine interne Revision als unabhängiges Prüfungsorgan,
4. eine angemessene IT- und Systeminfrastruktur, die den aufsichtlichen Anforderungen genügt."""
    },
    {
        "category": "wphg_kwg",
        "filename": "wphg_paragraph_63_80.txt",
        "language": "de",
        "source_document": "Wertpapierhandelsgesetz (WpHG)",
        "article_section_id": "§ 63, § 80 WpHG",
        "content": """§ 63 WpHG: Allgemeine Verhaltensregeln; automatisierte Anlageberatung
(1) Ein Wertpapierdienstleistungsunternehmen ist verpflichtet, Wertpapierdienstleistungen und Wertpapiernebendienstleistungen ehrlich, redlich und professionell im bestmöglichen Interesse seiner Kunden zu erbringen.
(4) Bei automatisierter Anlageberatung (Robo-Advice) und automatisierten Portfolioverwaltungssystemen muss das Institut sicherstellen, dass die Algorithmen den Kundenprofilen, Anlagezielen und der Verlusttragfähigkeit des Kunden entsprechen.

§ 80 WpHG: Organisationspflichten
(1) Ein Wertpapierdienstleistungsunternehmen muss angemessene Grundsätze und Verfahren schaffen, um sicherzustellen, dass die gesetzlichen Pflichten eingehalten werden. Bei algorithmischem Handel und algorithmischer Kundenberatung sind Systeme zur Risikobegrenzung und Unterbrechung des automatisierten Prozesses (Notfallmechanismen) vorzuhalten."""
    },
]


def ensure_corpus_directories(base_dir: str) -> Dict[str, Path]:
    """Ensures category subdirectories exist in knowledge_base/."""
    base_path = Path(base_dir)
    categories = ["eu_ai_act", "bafin", "wphg_kwg", "uploaded"]
    paths = {}
    for cat in categories:
        cat_path = base_path / cat
        cat_path.mkdir(parents=True, exist_ok=True)
        paths[cat] = cat_path
    return paths


def split_legal_document(text: str, source_doc: str, default_sec: str, language: str) -> List[Document]:
    """Splits legal text honoring Article / § / Section boundaries."""
    # Pattern matching Article X, § Y, or Section Z headers
    pattern = re.compile(r"((?:Article|Artikel|§|Section|ANNEX|MaRisk|Principle)\s+[^\n:]+[:\n])", re.IGNORECASE)
    splits = pattern.split(text)

    documents = []
    if len(splits) <= 1:
        # No major sub-headings found, return as single document
        doc = Document(
            page_content=text.strip(),
            metadata={
                "source_document": source_doc,
                "article_section_id": default_sec,
                "language": language,
                "passage_id": f"{source_doc}::{default_sec}",
            }
        )
        return [doc]

    current_header = default_sec
    for i in range(1, len(splits), 2):
        header = splits[i].strip()
        body = splits[i + 1].strip() if (i + 1) < len(splits) else ""
        content = f"{header}\n{body}".strip()
        if content:
            clean_header = header.rstrip(":\n")
            doc = Document(
                page_content=content,
                metadata={
                    "source_document": source_doc,
                    "article_section_id": clean_header,
                    "language": language,
                    "passage_id": f"{source_doc}::{clean_header}",
                }
            )
            documents.append(doc)

    return documents


def ingest_all_documents(kb_dir: Optional[str] = None) -> List[Document]:
    """Scans knowledge_base subdirectories, writes seed documents if empty, and builds hybrid index."""
    target_dir = kb_dir or settings.KNOWLEDGE_BASE_DIR
    category_paths = ensure_corpus_directories(target_dir)

    all_chunks: List[Document] = []

    # 1. Process seed corpus into knowledge base folders
    for seed in SEED_REGULATORY_CORPUS:
        cat = seed["category"]
        file_path = category_paths[cat] / seed["filename"]

        # Write seed file if it doesn't already exist locally
        if not file_path.exists():
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(seed["content"])
            logger.info("Saved fresh regulatory document locally: %s", file_path)
        else:
            logger.info("Reading existing regulatory document: %s", file_path)

        with open(file_path, "r", encoding="utf-8") as f:
            raw_text = f.read()

        chunks = split_legal_document(
            text=raw_text,
            source_doc=seed["source_document"],
            default_sec=seed["article_section_id"],
            language=seed["language"],
        )
        all_chunks.extend(chunks)

    # 2. Also check for any user-uploaded files under uploaded/
    uploaded_path = category_paths["uploaded"]
    for uploaded_file in uploaded_path.glob("*.txt"):
        try:
            with open(uploaded_file, "r", encoding="utf-8") as f:
                content = f.read()
            chunks = split_legal_document(
                text=content,
                source_doc=f"Uploaded Policy: {uploaded_file.name}",
                default_sec="Uploaded Control",
                language="en",
            )
            all_chunks.extend(chunks)
            logger.info("Ingested uploaded document: %s (%d chunks)", uploaded_file.name, len(chunks))
        except Exception as e:
            logger.error("Error reading uploaded document %s: %s", uploaded_file, e)

    # 3. Index chunks into dense vector store and separate BM25 indexes
    logger.info("Indexing %d total regulatory chunks...", len(all_chunks))
    vector_store_manager.add_documents(all_chunks)
    hybrid_retriever.build_bm25_indexes(all_chunks)
    logger.info("Hybrid ingestion complete. Total chunks indexed: %d", len(all_chunks))

    return all_chunks
