# # ----------------------------- Notebook input -----------------------------
# raw_sdlc_requirements = """
# DEMO-SRS-107: Assign every new requirement a unique, immutable ID.
# TEST-UNSAT-03: Every new requirement shall reuse an existing requirement identifier.
# DEMO-SRS-122: Convert attribute values when an attribute type changes.
# TEST-UNSAT-04: Attribute values shall never be converted when the attribute type changes.
# """

# # Step 1 only: create requirements_input.json without calling an LLM
# # requirements_input = requirements_text_to_json(raw_sdlc_requirements, "DEMO-001")
# # print(json.dumps(requirements_input, indent=2, ensure_ascii=False))

# # Full run after setting LLM_PROVIDER, LLM_MODEL and API key in environment:
# # output = run_pipeline_from_text(raw_sdlc_requirements, "DEMO-001", enumerate_all=True)
# # print(json.dumps(output["report"], indent=2, ensure_ascii=False))




# Notebook-ready SDLC requirements pipeline:
# raw text -> requirements_input.json -> LLM IR -> Z3 -> SMT-LIB -> core/MUS/report
# Install: %pip install -U openai google-genai z3-solver python-dotenv
 
from __future__ import annotations
import itertools, json, os, re
from pathlib import Path
from typing import Any, Dict, List, Set
from dotenv import load_dotenv
from z3 import *

import os
 
os.environ["AZURE_OPENAI_API_KEY"] = "your api key"
os.environ["AZURE_OPENAI_ENDPOINT"] = "your endpoint"
os.environ["AZURE_OPENAI_API_VERSION"] = "2024-12-01-preview"
 
# Use your Azure deployment name here
os.environ["LLM_PROVIDER"] = "azure"
os.environ["LLM_MODEL"] = "gpt-4o"
#load_dotenv()
 
# ------------------------- Raw text -> input JSON -------------------------
REQ_ID = re.compile(r"^\s*([A-Za-z][A-Za-z0-9_-]*-\d+)\s*:\s*(.+?)\s*$")
NUMBERED = re.compile(r"^\s*\d+[.)]\s+(.+?)\s*$")
BULLET = re.compile(r"^\s*[-*]\s+(.+?)\s*$")
 
def requirements_text_to_json(raw_text: str, document_id="SDLC-001",
                              auto_id_prefix="REQ",
                              output_path="requirements_input.json"):
    if not raw_text or not raw_text.strip():
        raise ValueError("Requirement text is empty")
    reqs, used, counter = [], set(), 1
    def auto_id():
        nonlocal counter
        while True:
            x = f"{auto_id_prefix}-{counter:03d}"; counter += 1
            if x not in used: return x
    for original in raw_text.splitlines():
        line = re.sub(r"<br\s*/?>", "", original, flags=re.I).strip()
        if not line: continue
        m, n, b = REQ_ID.match(line), NUMBERED.match(line), BULLET.match(line)
        if m:
            rid, statement = m.group(1).upper(), m.group(2).strip()
            if rid in used: raise ValueError(f"Duplicate requirement ID: {rid}")
        elif n or b:
            rid, statement = auto_id(), (n or b).group(1).strip()
        elif re.search(r"\b(shall|must|should|may|will)\b", line, re.I):
            rid, statement = auto_id(), line
        elif reqs:
            reqs[-1]["text"] += " " + line
            continue
        else:
            rid, statement = auto_id(), line
        used.add(rid); reqs.append({"requirement_id": rid, "text": statement})
    data = {"document_id": document_id, "requirements": reqs}
    Path(output_path).write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return data
 
def load_sdlc_text_file(path, document_id="SDLC-001"):
    return requirements_text_to_json(Path(path).read_text(encoding="utf-8"), document_id)
 
# ------------------------------ LLM client -------------------------------
def parse_json(text):
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text.strip())
    try: return json.loads(text)
    except json.JSONDecodeError: return json.loads(text[text.index('{'):text.rindex('}')+1])
 
class LLM:
    def __init__(self, provider=None, model=None):
 
        self.provider = (
            provider or os.getenv("LLM_PROVIDER", "azure")
        ).lower()
 
        self.model = model or os.getenv("LLM_MODEL")
 
        if not self.model:
            raise ValueError("Set LLM_MODEL")
 
        if self.provider == "azure":
 
            from openai import AzureOpenAI
 
            api_key = os.getenv("AZURE_OPENAI_API_KEY")
            endpoint = os.getenv("AZURE_OPENAI_ENDPOINT")
            api_version = os.getenv(
                "AZURE_OPENAI_API_VERSION",
                "2024-12-01-preview"
            )
 
            if not api_key:
                raise EnvironmentError(
                    "Set AZURE_OPENAI_API_KEY"
                )
 
            if not endpoint:
                raise EnvironmentError(
                    "Set AZURE_OPENAI_ENDPOINT"
                )
 
            self.client = AzureOpenAI(
                api_key=api_key,
                api_version=api_version,
                azure_endpoint=endpoint
            )
 
        elif self.provider == "gemini":
 
            from google import genai
 
            if not (
                os.getenv("GEMINI_API_KEY")
                or os.getenv("GOOGLE_API_KEY")
            ):
                raise EnvironmentError(
                    "Set GEMINI_API_KEY or GOOGLE_API_KEY"
                )
 
            self.client = genai.Client()
 
        else:
            raise ValueError(
                "Provider must be azure or gemini"
            )
 
    def json(self, prompt):
 
        if self.provider == "azure":
 
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content":
                        "Return exactly one valid JSON object and no markdown."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                temperature=0
            )
 
            return parse_json(
                response.choices[0].message.content
            )
 
        response = self.client.models.generate_content(
            model=self.model,
            contents=
            "Return exactly one valid JSON object and no markdown.\n"
            + prompt
        )
 
        return parse_json(response.text)
 
IR_PROMPT = r'''
Convert the INPUT requirements into IR version 2.1.

Return exactly one valid JSON object with this structure:

{
  "document_id": "...",
  "ir_version": "2.1",
  "canonical_registry": {
    "actors": [],
    "entities": [],
    "events": [],
    "states": [],
    "terms": []
  },
  "domain_axioms": [
    {
      "type": "enum",
      "symbol": "shared_property_symbol",
      "values": ["value_1", "value_2"]
    }
  ],
  "ir": [
    {
      "requirement_id": "...",
      "ir_status": "complete|needs_review",
      "requirement_type": "functional|performance|constraint",
      "statement": {
        "modality": "shall|shall_not|may",
        "actors": [],
        "actions": [],
        "objects": [],
        "conditions": [],
        "effects": [],
        "authorization": {
          "required": false,
          "actor_requirements": []
        },
        "constraints": [],
        "temporal": {
          "has_temporal_constraint": false
        },
        "quantification": {
          "quantifier": "none_explicit|every|all|some",
          "scope_refs": []
        }
      },
      "entities": [],
      "events": [],
      "states": [],
      "dependencies": [],
      "traceability": {
        "source_requirement_id": "...",
        "original_text": "...",
        "refined_text": "..."
      },
      "unresolved": [],
      "formalization": {
        "scenario_key": "normalized_shared_trigger",
        "antecedent": {
          "all": [
            {
              "symbol": "trigger_symbol",
              "sort": "Bool",
              "op": "is_true"
            }
          ]
        },
        "consequent": {
          "all": [
            {
              "symbol": "outcome_symbol",
              "sort": "Bool",
              "op": "is_true"
            }
          ]
        }
      }
    }
  ]
}

FORMALIZATION RULES:

1. Preserve every input requirement ID and original text exactly.

2. Produce exactly one IR entry for every input requirement.

3. Use only these sorts:
   Bool
   Int
   Real
   String
   Enum:Name

4. Use only these operators:
   is_true
   is_false
   =
   !=
   <
   <=
   >
   >=

5. Antecedent atoms represent when a requirement applies.

6. Consequent atoms represent the mandatory or prohibited outcome.

7. Requirements with equivalent applicability conditions must use:
   - the same scenario_key,
   - the same antecedent symbols,
   - the same symbol sorts.

8. Normalize synonymous triggers to one canonical event symbol.
   Examples:
   - "when an attribute type changes"
   - "if the attribute type is changed"
   Both must use:
   attribute_type_changed

9. Requirements regulating the same property, action, state, or decision
   must reuse the same canonical consequent symbol.

10. Express a required action and its prohibition using the same Bool symbol.

    Required:
    {
      "symbol": "attribute_values_converted",
      "sort": "Bool",
      "op": "is_true"
    }

    Prohibited:
    {
      "symbol": "attribute_values_converted",
      "sort": "Bool",
      "op": "is_false"
    }

11. Never create separate Boolean symbols for positive and negative forms.

    Incorrect:
    convert_attribute_values
    never_convert_attribute_values

    Correct:
    attribute_values_converted is_true
    attribute_values_converted is_false

12. Express mutually exclusive alternatives as different values of one
    shared Enum symbol.

    Example:
    {
      "type": "enum",
      "symbol": "identifier_assignment_policy",
      "values": [
        "unique_new_identifier",
        "reuse_existing_identifier"
      ]
    }

    The corresponding consequences must use:

    {
      "symbol": "identifier_assignment_policy",
      "sort": "Enum:IdentifierAssignmentPolicy",
      "op": "=",
      "value": "unique_new_identifier"
    }

    and:

    {
      "symbol": "identifier_assignment_policy",
      "sort": "Enum:IdentifierAssignmentPolicy",
      "op": "=",
      "value": "reuse_existing_identifier"
    }

13. The Enum atom symbol must exactly match the symbol in its enum
    domain axiom.

14. Do not represent mutually exclusive alternatives as independent
    Boolean symbols.

15. If a requirement contains multiple obligations, include all obligations
    as separate atoms inside consequent.all.

16. For "unique and immutable identifier":
    - represent the identifier assignment strategy using a shared Enum;
    - represent immutability using a separate Bool property.

17. For "shall never", "must not", "shall not", or an equivalent
    prohibition:

    - use modality "shall_not";
    - use is_false when prohibiting a Boolean action or property;
    - use != when prohibiting one specific Enum, String, Int, or Real value;
    - use the appropriate inverse numeric boundary when prohibiting a
      numeric range;
    - reuse the same canonical symbol as the corresponding positive form.

18. Requirements that genuinely conflict must become logically incompatible
when their common applicability conditions are satisfiable.
Do not make requirements logically incompatible unless:
- they share equivalent applicability conditions;
- their guards have a feasible overlap;
- or an explicit dependency makes their outcomes apply together.

19. Do not weaken conflicts by:
    - assigning different scenario keys,
    - creating different symbols for equivalent outcomes,
    - omitting the antecedent,
    - using unrelated Boolean variables.

20. Use snake_case canonical symbols containing only letters, digits,
    and underscores.

21. Reuse canonical actors, entities, events, states, and terms throughout
    the entire document.

22. Do not invent business rules, values, conditions, exceptions, actors,
    or dependencies not present in the input.

23. If a requirement cannot be formalized without inventing information:
    - set ir_status to "needs_review";
    - describe the issue in unresolved;
    - still provide the safest partial formalization possible.

24. Return valid JSON only.
    Do not return Markdown, comments, explanations, or code fences.

25. Canonicalize equivalent applicability conditions across the complete
    requirement set.

    Requirements applying under semantically equivalent conditions must use:
    - the same scenario_key;
    - the same antecedent symbols;
    - the same symbol sorts;
    - the same units of measurement.

26. Construct scenario_key from the normalized business event, relevant
    state, actor scope, and operating context.

    The scenario_key must:
    - use snake_case;
    - describe only the applicability context;
    - not contain requirement IDs;
    - not contain modal words such as shall, must, may, or should;
    - be reused across requirements with equivalent applicability conditions.

27. Normalize synonymous conditions before generating scenario keys and
    symbols.

    Examples of equivalent expressions include:
    - "falls below N" and "is less than N";
    - "does not exceed N" and "is at most N";
    - "at least N" and "greater than or equal to N";
    - "is disabled" and "is not enabled";
    - "is prohibited" and "is not permitted";
    - "must occur" and "is required to occur";
    - "must not occur" and "is prohibited from occurring".

28. Represent each distinct condition using a canonical antecedent atom.

    Conditions referring to the same event, state, role, resource,
    measurement, action, or entity property must reuse the same canonical
    symbol throughout the document.

29. Use one canonical Boolean symbol for positive and negative forms of the
    same action, permission, state, availability, or property.

    Required, enabled, available, authorized, or performed:

    {
      "symbol": "<canonical_boolean_symbol>",
      "sort": "Bool",
      "op": "is_true"
    }

    Prohibited, disabled, unavailable, unauthorized, or not performed:

    {
      "symbol": "<canonical_boolean_symbol>",
      "sort": "Bool",
      "op": "is_false"
    }

30. Do not create separate Boolean symbols for:
    - an action and its prohibition;
    - a permission and its denial;
    - an enabled state and its disabled state;
    - an available state and its unavailable state.

31. Normalize concrete actions to a shared abstract operation when that
    relationship is explicitly stated or follows directly from the meaning
    provided in the requirements.

    Examples:
    - writing an audit record to disk is a disk write operation;
    - downloading a protected file is a protected-file access operation;
    - opening a database connection consumes a database connection;
    - sending stored data requires a data-read operation;
    - assigning a permission is an authorization decision.

    Do not use external domain assumptions to create such relationships.

32. If one requirement prohibits an abstract operation and another
    requirement mandates a concrete action that necessarily performs that
    operation in the same scenario, formalize both requirements using the
    same canonical operation symbol.

33. Preserve all explicitly stated applicability conditions as antecedent
    atoms.

    Do not move a guard, trigger, state, actor qualification, platform,
    resource condition, or threshold from the antecedent into the
    consequent.

34. When guards partially overlap, preserve the complete guard of each
    requirement.

    Treat the requirements as simultaneously applicable only when their
    antecedents have a feasible intersection that is:
    - explicitly stated;
    - logically derivable from the input;
    - or represented by an explicit overlap scenario in the input.

35. Do not assume that two different guards overlap merely to manufacture
    a conflict.

    If guard overlap cannot be established from the input, set ir_status
    to "needs_review" and describe the missing overlap information in
    unresolved.

36. Normalize numeric boundary expressions as follows:

    - "below N" or "less than N" -> <
    - "at most N" -> <=
    - "does not exceed N" -> <=
    - "above N" or "greater than N" -> >
    - "at least N" -> >=
    - "exactly N" -> =
    - "between A and B inclusive" -> >= A and <= B
    - "between A and B exclusive" -> > A and < B

37. Requirements constraining the same measurement must reuse:
    - the same canonical symbol;
    - the same numeric sort;
    - the same canonical unit;
    - the same measurement scope.

38. Use Int for discrete counts and Real for continuous measurements,
    percentages, ratios, monetary values containing decimals, and
    non-integral durations.

39. Do not treat values expressed in different units as constraints over
    the same symbol until they have been converted to one canonical unit.

    If an exact standard conversion is available, convert the values and
    record the canonical unit in the symbol or term registry.

    If conversion is ambiguous, set ir_status to "needs_review".

40. Represent different values assigned to the same deterministic output
    using one shared symbol.

    If two simultaneously applicable requirements assign different values
    to the same single-valued output, use:
    - the same output symbol;
    - the same sort;
    - the corresponding different values.

41. Do not treat different deterministic output values as cumulative,
    additive, prioritized, or multi-valued unless the requirements
    explicitly define a combination, priority, or override policy.

42. For mutually exclusive named output alternatives, use one Enum symbol.

    For numeric outputs such as percentages, durations, counts, limits,
    and monetary values, use one shared Int or Real symbol.

43. Distinguish pre-transition and post-transition values when an action
    changes a state or measured property.

    Use canonical naming patterns such as:

    <property>_before_<transition>
    <property>_after_<transition>

44. Requirements constraining the same post-transition value must reuse
    the same post-transition symbol.

    Do not use the pre-transition symbol for a post-transition invariant
    or transition result.

45. Preserve explicitly stated transition relationships.

    If the input explicitly states that a transition adds, removes,
    consumes, allocates, or releases a quantity, formalize the resulting
    post-state relationship when the IR supports it.

    Examples:

    post_value = pre_value + added_value
    post_value = pre_value - removed_value
    remaining_capacity = total_capacity - allocated_capacity

46. Preserve explicitly stated dependencies between services, features,
    operations, resources, roles, permissions, and actions.

    If the input states that A requires B, do not represent A and B as
    unrelated outcomes.

47. When a required action has a mandatory prerequisite, requiring the
    action in a scenario also requires that prerequisite in that scenario.

    If another applicable requirement prohibits the prerequisite, reuse
    the same canonical prerequisite symbol so the incompatibility is
    visible to the solver.

48. Do not infer a dependency based only on external business or technical
    knowledge.

    A dependency may be formalized only when it is:
    - explicitly stated in the requirements;
    - defined in a supplied domain axiom;
    - or directly contained in the meaning of the specified operation.

49. Preserve arithmetic relationships explicitly stated in the requirements
    when the IR supports arithmetic expressions.

    Examples include:

    total = component_1 + component_2
    total >= count * duration_per_item
    total_allocation = sum_of_allocations
    post_value = pre_value + transition_delta

50. Do not replace a multi-variable arithmetic relationship with unrelated
    atomic bounds.

    If the current IR cannot represent the required arithmetic relationship:
    - set ir_status to "needs_review";
    - identify the unsupported relationship in unresolved;
    - provide the safest partial formalization;
    - do not invent a simplified contradiction.

51. Detect valid incompatibility patterns under a feasible shared context.

    Valid patterns include:
    - P and Not(P);
    - X = A 

58. Every Enum value referenced by an antecedent or consequent atom must
    be declared in the corresponding enum domain axiom.

59. Do not invent sentinel Enum values such as:
    - none;
    - unknown;
    - unassigned;
    - not_applicable;
    - undefined;

    unless that value is explicitly permitted by the input requirements.

60. When a requirement excludes every permitted value of an Enum, represent
    the exclusions using separate != atoms over the same Enum symbol.

    For example, if the permitted values are category_a and category_b,
    represent "neither category_a nor category_b" as:

    {
      "symbol": "classification",
      "sort": "Enum:Classification",
      "op": "!=",
      "value": "category_a"
    }

    and:

    {
      "symbol": "classification",
      "sort": "Enum:Classification",
      "op": "!=",
      "value": "category_b"
    }

    Do not represent this as:

    {
      "symbol": "classification",
      "sort": "Enum:Classification",
      "op": "=",
      "value": "none"
    }

61. Before returning the IR, verify that every value used with an Enum
    equality or inequality operator exists in that Enum's domain axiom.
INPUT:
'''
 
def make_ir(data, llm, output_path="requirements_ir.json"):
    ir = llm.json(IR_PROMPT + json.dumps(data, indent=2, ensure_ascii=False))
    expected = {x["requirement_id"] for x in data["requirements"]}
    actual = {x.get("requirement_id") for x in ir.get("ir", [])}
    if expected != actual: raise ValueError(f"IR IDs differ: {expected} != {actual}")
    for x in ir["ir"]:
        if not x.get("formalization", {}).get("scenario_key"):
            raise ValueError(f"Missing formalization for {x['requirement_id']}")
    Path(output_path).write_text(json.dumps(ir, indent=2, ensure_ascii=False), encoding="utf-8")
    return ir
 
# ------------------------------ IR -> Z3 ---------------------------------
def safe(s):
    x = re.sub(r"[^A-Za-z0-9_]", "_", str(s)); return x if x and not x[0].isdigit() else "v_"+x
 
class Compiler:
    def __init__(self, ir):
        self.ir, self.vars, self.sorts, self.enums = ir, {}, {}, {}
        for ax in ir.get("domain_axioms", []):
            if ax.get("type") == "enum":
                self.enums[safe(ax["symbol"])] = {str(v): i for i,v in enumerate(ax["values"])}
    def var(self, symbol, sort):
        n, kind = safe(symbol), ("Enum" if sort.startswith("Enum:") else sort)
        if n in self.sorts and self.sorts[n] != kind: raise ValueError(f"Sort conflict: {n}")
        self.sorts[n] = kind
        if n not in self.vars:
            self.vars[n] = {"Bool":Bool,"Int":Int,"Enum":Int,"Real":Real,"String":String}[kind](n)
        return self.vars[n]
    def atom(self, a):
        v, op, sort, value = self.var(a["symbol"], a["sort"]), a["op"], a["sort"], a.get("value")
        if op == "is_true": return v
        if op == "is_false": return Not(v)
        if sort.startswith("Enum:"):
            mapping = self.enums.get(safe(a["symbol"])); c = IntVal(mapping[str(value)])
        elif sort == "Int": c = IntVal(int(value))
        elif sort == "Real": c = RealVal(str(value))
        elif sort == "String": c = StringVal(str(value))
        else: c = BoolVal(bool(value))
        return {"=":v==c,"!=":v!=c,"<":v<c,"<=":v<=c,">":v>c,">=":v>=c}[op]
    def conj(self, atoms):
        xs = [self.atom(a) for a in atoms]; return And(*xs) if xs else BoolVal(True)
    def compile(self):
        s, reqs, scenarios = Solver(), {}, {}
        for symbol, mapping in self.enums.items():
            v=self.var(symbol,"Enum:X"); s.add(v>=0,v<len(mapping))
        for r in self.ir["ir"]:
            rid, f = r["requirement_id"], r["formalization"]
            ant=self.conj(f.get("antecedent",{}).get("all",[])); cons=self.conj(f.get("consequent",{}).get("all",[]))
            e=Bool("ENABLE_"+safe(rid)); s.add(Implies(e,Implies(ant,cons))); reqs[rid]=e
            key=f["scenario_key"]; sc=scenarios.setdefault(key,Bool("SCENARIO_"+safe(key))); s.add(Implies(sc,ant))
        return s, reqs, scenarios
 
# ------------------------- SAT, core, and MUS -----------------------------
def check(s, reqs, scenarios, ids=None):
    ids = list(reqs) if ids is None else list(ids)
    result=s.check(*([reqs[x] for x in ids]+list(scenarios.values())))
    return result, ([str(x) for x in s.unsat_core()] if result==unsat else [])
 
def core_ids(reqs, core):
    rev={str(v):k for k,v in reqs.items()}; return [rev[x] for x in core if x in rev]
 
def minimize_core(s, reqs, scenarios, ids):
    mus=list(dict.fromkeys(ids)); assert check(s,reqs,scenarios,mus)[0]==unsat
    i=0
    while i<len(mus):
        trial=mus[:i]+mus[i+1:]
        if trial and check(s,reqs,scenarios,trial)[0]==unsat: mus=trial
        else: i+=1
    return mus
 
def all_muses_small(s, reqs, scenarios, limit=20):
    ids=list(reqs)
    if len(ids)>limit: raise ValueError("Use MARCO for more than 20 requirements")
    out: List[Set[str]]=[]
    for n in range(1,len(ids)+1):
        for c in itertools.combinations(ids,n):
            cs=set(c)
            if any(m<=cs for m in out): continue
            if check(s,reqs,scenarios,c)[0]==unsat: out.append(cs)
    return [sorted(x) for x in out]
 
def export_smt2(s, reqs, scenarios, path="requirements_model.smt2"):
    asm=list(reqs.values())+list(scenarios.values())
    text=re.sub(r"\(check-sat\)\s*$","",s.to_smt2().strip())
    text+="\n(check-sat-assuming ("+" ".join(map(str,asm))+"))\n(get-unsat-core)\n"
    Path(path).write_text(text,encoding="utf-8")
 
def report(data, ir, result, core, muses, path="consistency_report.json"):
    by_text = {
        x["requirement_id"]: x["text"]
        for x in data["requirements"]
    }

    by_ir = {
        x["requirement_id"]: x
        for x in ir["ir"]
    }

    def conflict_reason(ids):
        entries = [by_ir[x] for x in ids]
        scenarios = {
            x["formalization"]["scenario_key"]
            for x in entries
        }

        outcomes = []
        for x in entries:
            atoms = x["formalization"]["consequent"].get("all", [])
            for atom in atoms:
                outcomes.append({
                    "requirement_id": x["requirement_id"],
                    "symbol": atom["symbol"],
                    "operator": atom["op"],
                    "value": atom.get("value")
                })

        scenario = next(iter(scenarios)) if len(scenarios) == 1 else "shared context"

        return (
            f"These requirements apply to the same scenario '{scenario}' "
            f"but impose incompatible outcomes: "
            + "; ".join(
                f"{x['requirement_id']} requires "
                f"{x['symbol']} {x['operator']}"
                + (f" {x['value']}" if x["value"] is not None else "")
                for x in outcomes
            )
            + "."
        )

    obj = {
        "document_id": data["document_id"],
        "solver": "Z3",
        "status": str(result).upper(),
        "raw_unsat_core": core,
        "mus_count": len(muses),
        "conflicts": [
            {
                "conflict_id": f"MUS-{i:03d}",
                "requirement_ids": mus,
                "conflict_reason": conflict_reason(mus),
                "requirements": [
                    {
                        "requirement_id": rid,
                        "text": by_text[rid]
                    }
                    for rid in mus
                ]
            }
            for i, mus in enumerate(muses, 1)
        ]
    }

    Path(path).write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )
    return obj
 
# -------------------------- End-to-end entrypoints ------------------------
def run_pipeline(data, provider=None, model=None, enumerate_all=False):
    ir=make_ir(data,LLM(provider,model)); s,reqs,scenarios=Compiler(ir).compile()
    result,core=check(s,reqs,scenarios); export_smt2(s,reqs,scenarios); muses=[]
    if result==unsat:
        muses=[minimize_core(s,reqs,scenarios,core_ids(reqs,core))]
        if enumerate_all: muses=all_muses_small(s,reqs,scenarios)
    return {"ir":ir,"report":report(data,ir,result,core,muses)}
 
def run_pipeline_from_text(raw_text, document_id="SDLC-001", provider=None,
                           model=None, enumerate_all=False):
    data=requirements_text_to_json(raw_text,document_id)
    return run_pipeline(data,provider,model,enumerate_all)
 
# ----------------------------- Notebook input -----------------------------
raw_sdlc_requirements = """
SOD-1301: When an engineer who owns a repository attempts to approve their own pull request, the engineer shall not be authorized to approve the pull request.

SOD-1302: When an engineer who owns a repository attempts to approve their own pull request, the engineer shall be authorized, as the repository owner, to approve and merge the pull request.
"""
 
# Step 1 only: create requirements_input.json without calling an LLM
requirements_input = requirements_text_to_json(raw_sdlc_requirements, "DEMO-001")
print(json.dumps(requirements_input, indent=2, ensure_ascii=False))
 
# Full run after setting LLM_PROVIDER, LLM_MODEL and API key in environment:
output = run_pipeline_from_text(raw_sdlc_requirements, "DEMO-001", enumerate_all=True)
print(json.dumps(output["report"], indent=2, ensure_ascii=False))
