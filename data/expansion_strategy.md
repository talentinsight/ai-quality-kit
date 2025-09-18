# 🚀 Test Data Expansion Strategy

## 📊 **Current State Analysis**

### Built-in Data Volume:
- **Safety**: 29 base tests (data/golden/safety.jsonl)
- **Red Team**: ~60 attack scenarios (data/red_team/attacks.yaml)
- **Templates**: ~20 examples per category (data/templates/)

### Expansion Mechanisms:
1. **Expanded Datasets** (data/expanded/YYYYMMDD/)
2. **User Upload Merge** (intake_bundle_dir)
3. **Subtest Multipliers** (subtype variations)

## 🎯 **Expansion Strategies**

### 1. **Automated Test Generation** 🤖
```python
# Generate variations programmatically
def expand_safety_tests(base_tests, multiplier=5):
    expanded = []
    for test in base_tests:
        # Paraphrase variations
        for i in range(multiplier):
            expanded.append({
                "test_id": f"{test['test_id']}_var_{i}",
                "query": paraphrase_query(test['query'], style=i),
                "category": test['category'],
                "severity": test['severity']
            })
    return expanded
```

### 2. **Industry Dataset Integration** 📚
```yaml
# Add external datasets
external_sources:
  - name: "OWASP_LLM_Top10"
    path: "data/external/owasp_llm_tests.jsonl"
    count: 200
  - name: "HatEval_2019" 
    path: "data/external/hateval_tests.jsonl"
    count: 500
  - name: "ToxicityDetection"
    path: "data/external/toxicity_tests.jsonl" 
    count: 1000
```

### 3. **Subtest Matrix Expansion** 📈
```python
# Current subtests per category
safety_subtests = {
    "toxicity": ["explicit", "implicit", "contextual"],
    "hate": ["targeted", "general", "coded"],
    "violence": ["graphic", "threat", "instructional"]
}

# Expanded subtests matrix
expanded_subtests = {
    "toxicity": [
        "explicit", "implicit", "contextual", 
        "multilingual", "encoded", "euphemistic",
        "role_play", "hypothetical", "academic"
    ],
    "hate": [
        "targeted", "general", "coded",
        "intersectional", "historical", "cultural",
        "dog_whistle", "stereotype", "dehumanizing"
    ]
}
```

### 4. **Dynamic Test Generation** ⚡
```python
# Generate tests based on user domain
def generate_domain_tests(domain: str, count: int = 50):
    """Generate domain-specific safety tests"""
    if domain == "healthcare":
        return generate_medical_safety_tests(count)
    elif domain == "finance":
        return generate_financial_safety_tests(count)
    elif domain == "education":
        return generate_educational_safety_tests(count)
```

## 📋 **Implementation Plan**

### Phase 1: **Immediate Expansion** (1-2 days)
- [ ] Add 200+ safety test variations to data/expanded/
- [ ] Add 300+ red team attack scenarios  
- [ ] Implement paraphrase generation for existing tests
- [ ] Add multilingual test variants (5 languages)

### Phase 2: **External Integration** (1 week)
- [ ] Integrate OWASP LLM Top 10 test suite
- [ ] Add HatEval and ToxicityDetection datasets
- [ ] Implement dataset format converters
- [ ] Add dataset version management

### Phase 3: **Dynamic Generation** (2 weeks)
- [ ] Implement LLM-based test generation
- [ ] Add domain-specific test generators
- [ ] Implement difficulty progression (easy → hard)
- [ ] Add adversarial test evolution

## 🔧 **Technical Implementation**

### Data Structure:
```
data/
├── golden/                 # Core 29 tests (baseline)
├── expanded/              # Generated variations (1000+)
│   ├── 20250825/         # Version-controlled
│   ├── 20250901/         # New versions
│   └── latest/           # Symlink to current
├── external/              # Industry datasets
│   ├── owasp/
│   ├── hateval/
│   └── toxicity/
└── generated/             # Dynamic generation
    ├── domain_specific/
    ├── multilingual/
    └── adversarial/
```

### User Data Merge Priority:
1. **User Upload** (highest priority)
2. **Domain Generated** (if domain specified)  
3. **Expanded Dataset** (version-specific)
4. **External Datasets** (industry standard)
5. **Golden Dataset** (fallback baseline)

## 📊 **Expected Results**

### Before Expansion:
- Safety: 29 tests
- Red Team: 60 attacks
- **Total**: ~90 test cases

### After Expansion:
- Safety: 500+ tests (17x increase)
- Red Team: 800+ attacks (13x increase)  
- **Total**: ~1300+ test cases (14x increase)

### Coverage Improvement:
- **Multilingual**: 5 languages
- **Domain-Specific**: 8 industries
- **Difficulty Levels**: 3 tiers (basic/intermediate/advanced)
- **Attack Sophistication**: 4 levels (script kiddie → APT)

---

**Next Steps**: Implement Phase 1 expansion to immediately improve test coverage while maintaining format compatibility.
