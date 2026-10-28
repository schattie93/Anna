"""Feste Auswahllisten (Textbausteine). Später über die Oberfläche pflegbar."""

RED_FLAGS: dict[str, str] = {
    "weight_loss": "Ungewollter Gewichtsverlust",
    "night_pain": "Nächtlicher Ruheschmerz",
    "fever": "Fieber / allgemeines Krankheitsgefühl",
    "cancer_history": "Tumorerkrankung in der Vorgeschichte",
    "trauma": "Relevantes Trauma",
    "neuro_deficit": "Neurologische Ausfälle (Kraft, Sensibilität)",
    "cauda_equina": "Blasen-/Mastdarmstörung, Reithosenanästhesie",
    "steroids": "Langzeit-Kortisoneinnahme / Osteoporose",
    "anticoagulants": "Gerinnungshemmer",
    "dizziness": "Schwindel, Sehstörungen, Sprech-/Schluckstörungen",
}

MEASURES: list[str] = [
    "Krankengymnastik (KG)",
    "KG am Gerät (KGG)",
    "KG-ZNS (Bobath/PNF)",
    "Manuelle Therapie (MT)",
    "Manuelle Lymphdrainage (MLD)",
    "Klassische Massage (KMT)",
    "Wärmetherapie",
    "Kältetherapie",
    "Elektrotherapie",
    "Ultraschall",
    "Taping",
    "Triggerpunkttherapie",
    "Faszientechniken",
    "Hausübungsprogramm erklärt",
    "Gangschule",
    "Atemtherapie",
]
