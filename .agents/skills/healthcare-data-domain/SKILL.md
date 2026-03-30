---
name: healthcare-data-domain
version: 0.1.0
description: >
  Healthcare data domain context covering FHIR, HL7, OMOP CDM, real-world evidence,
  and clinical terminology systems. Use when working on clinical data pipelines,
  EHR integrations, claims data products, HIPAA-governed data, OMOP transformations,
  or when the conversation involves PHI, ICD-10, SNOMED, CPT, LOINC, or RxNorm.
  Skip this skill for non-healthcare data products.
user-invocable: false
---

## When This Skill Applies

Activate when the data product involves: electronic health records (EHR), claims/billing data, clinical terminology, patient-level data, OMOP CDM, FHIR/HL7, or any data governed by HIPAA.

Do NOT activate for: general analytics, marketing data, financial data, or non-clinical datasets.

## Core Standards

**FHIR (Fast Healthcare Interoperability Resources)** - Modern API standard for health data exchange. Resource-based (Patient, Observation, MedicationRequest, Condition, Encounter). Use for real-time integrations and patient-facing apps.

**HL7 v2** - Legacy messaging standard still dominant in hospital systems. Pipe-delimited segments (MSH, PID, OBX). Expect to encounter this in any EHR integration project.

**OMOP CDM (Common Data Model)** - Research-optimized schema for observational health data. Core tables: PERSON, VISIT_OCCURRENCE, CONDITION_OCCURRENCE, DRUG_EXPOSURE, MEASUREMENT, OBSERVATION, PROCEDURE_OCCURRENCE. Use for analytics and real-world evidence studies.

## Clinical Terminology Systems

| System | What It Codes | Example |
|--------|--------------|---------|
| ICD-10-CM | Diagnoses | F32.1 (Major depressive disorder, single episode, moderate) |
| CPT | Procedures | 99213 (Office visit, established patient) |
| SNOMED CT | Clinical concepts | 73211009 (Diabetes mellitus) |
| LOINC | Lab tests/observations | 2345-7 (Glucose, serum/plasma) |
| RxNorm | Medications | 197361 (Sertraline 50mg tablet) |
| NDC | Drug packages | National Drug Code for specific manufacturer/package |

ALWAYS use standard terminology codes rather than free-text descriptions. Map to the appropriate code system for the use case.

## OMOP Analytics Patterns

The 30-40 normalized OMOP tables are wrong for analytics dashboards. Transform to star schema with strategic denormalization:
- Fact tables: Drug exposures, visits, conditions (events become facts)
- Dimension tables: Patient, drug, diagnosis
- Pre-calculated cohort definitions for common queries
- NEVER fully denormalize (One Big Table). Healthcare's many-to-many relationships cause exponential row growth.

## FHIR Gotchas

Common mistakes when working with FHIR resources:

| Gotcha | What Trips You Up | Fix |
|--------|-------------------|-----|
| Coding vs CodeableConcept | `Coding` is a single code. `CodeableConcept` wraps multiple codings with a display text. Most FHIR fields use CodeableConcept. | Always access `.coding[0].code`, not `.code` directly. |
| Patient.identifier vs Patient.id | `.id` is the FHIR server's internal ID. `.identifier` holds MRNs, SSNs, and other business identifiers. | Query by `.identifier.value` with the correct `.identifier.system`. |
| Observation.value[x] | Polymorphic field. Could be `valueQuantity`, `valueString`, `valueCodeableConcept`, or others. | Check the resource profile or test data to know which type your source sends. |
| Bundle pagination | Search results return pages of 20-50 resources. The full result set requires following `Bundle.link` where `relation = "next"`. | Always paginate. NEVER assume a single Bundle contains all results. |

## FHIR-to-OMOP Mapping

When transforming FHIR resources into OMOP CDM:

| FHIR Resource | OMOP Table | Key Mapping Notes |
|---------------|-----------|-------------------|
| Patient | person | Map `Patient.birthDate` → `year_of_birth`. Gender codes differ between systems. |
| Condition | condition_occurrence | `Condition.code` → `condition_concept_id` via SNOMED-to-OMOP vocabulary mapping. |
| Observation | measurement | Lab results map here. Use LOINC code from `Observation.code` for `measurement_concept_id`. |
| MedicationRequest | drug_exposure | Map RxNorm codes. `MedicationRequest.dosageInstruction` → `dose_value`/`dose_unit`. |
| Encounter | visit_occurrence | `Encounter.class` → `visit_concept_id`. Map inpatient/outpatient/emergency. |

## Common LOINC Codes for Vitals

| Vital Sign | LOINC Code | Units |
|------------|-----------|-------|
| Blood pressure, systolic | 8480-6 | mmHg |
| Blood pressure, diastolic | 8462-4 | mmHg |
| Heart rate | 8867-4 | /min |
| Body temperature | 8310-5 | Cel |
| Body weight | 29463-7 | kg |
| Body height | 8302-2 | cm |

## E&M Level Determination (2021 AMA/CMS MDM Guidelines)

E&M (Evaluation and Management) codes represent the office visit itself. The code selected depends on the complexity of Medical Decision Making (MDM).

### Code Ranges

| MDM Level | New Patient | Established Patient |
|---|---|---|
| Straightforward | 99202 | 99211 |
| Low | 99203 | 99212 |
| Moderate | 99204 | 99213 |
| High | 99205 | 99215 |

Note: 99201 was deleted in the 2021 guidelines.

### MDM Elements (2 of 3 must meet or exceed the level)

1. **Number/Complexity of Problems**: minimal, low, moderate, high
2. **Amount/Complexity of Data Reviewed**: minimal/none, limited, moderate, extensive
3. **Risk of Complications/Morbidity/Mortality**: minimal, low, moderate, high

### Key Rules
- Time-based coding is an alternative: total time on the date of encounter (includes documentation, care coordination, not just face-to-face)
- New vs Established: determined by whether the patient has been seen by the same provider or same specialty/group within the past 3 years
- The highest 2 of 3 elements determine the MDM level

## HIPAA Safe Harbor De-identification

CRITICAL: Any data product handling patient data must consider the 18 HIPAA identifiers. De-identification is required before data leaves a HIPAA-governed environment.

### The 18 Safe Harbor Identifiers

1. Names
2. Geographic data smaller than a state (street addresses, cities, ZIP codes — first 3 digits may be retained if population >20,000)
3. Dates (except year) directly related to an individual (birth date, admission date, discharge date, date of death, ages over 89)
4. Phone numbers
5. Fax numbers
6. Email addresses
7. Social Security numbers
8. Medical record numbers
9. Health plan beneficiary numbers
10. Account numbers
11. Certificate/license numbers
12. Vehicle identifiers and serial numbers
13. Device identifiers and serial numbers
14. Web URLs
15. IP addresses
16. Biometric identifiers (fingerprints, voiceprints)
17. Full-face photographs and comparable images
18. Any other unique identifying number, characteristic, or code

### De-identification Approaches
- **Safe Harbor**: Remove all 18 identifiers. No expert required. Simpler but more aggressive.
- **Expert Determination**: Statistician certifies re-identification risk is very small. Allows retaining some data.

This skill provides general domain context, not compliance advice. Involve your privacy officer and legal team for HIPAA compliance decisions.
