# RAG Test Data Upload Examples

Bu klasör, RAG Reliability & Robustness testleri için upload edilebilir örnek test datalarını içerir.

## 📁 Dosya Formatları

### 1. **Faithfulness Evaluation** (`rag_faithfulness_sample.jsonl`)
LLM'in verilen context'e ne kadar sadık kaldığını test eder.

**Format:**
```json
{
  "test_id": "faithfulness_01",
  "query": "Soru metni",
  "expected_answer": "Beklenen cevap (opsiyonel)",
  "context": ["Context paragraf 1", "Context paragraf 2"],
  "tags": ["kategori", "etiketler"]
}
```

### 2. **Context Recall** (`rag_context_recall_sample.jsonl`)
LLM'in context'ten ne kadar bilgi hatırladığını test eder.

**Format:** Faithfulness ile aynı format

### 3. **Answer Relevancy** (`rag_answer_relevancy_sample.jsonl`)
LLM'in cevabının soruya ne kadar uygun olduğunu test eder.

**Format:** Faithfulness ile aynı format

### 4. **Context Precision** (`rag_context_precision_sample.jsonl`)
Context'in ne kadar alakalı ve gereksiz bilgi içermediğini test eder.

**Format:** Faithfulness ile aynı format (alakasız context'ler dahil)

### 5. **Answer Correctness** (`rag_answer_correctness_sample.jsonl`)
LLM'in cevabının faktüel doğruluğunu test eder.

**Format:** Faithfulness ile aynı format (doğru cevaplar odaklı)

### 6. **Ground Truth Evaluation** (`rag_ground_truth_sample.jsonl`)
Kapsamlı Ragas değerlendirmesi için ground truth ile karşılaştırma.

**Format:**
```json
{
  "test_id": "ground_truth_01",
  "query": "Soru metni",
  "expected_answer": "Beklenen cevap",
  "context": ["Context paragrafları"],
  "ground_truth": "Kesin doğru cevap",
  "tags": ["kategori"]
}
```

### 7. **Prompt Robustness** (`prompt_robustness_sample.jsonl`)
Farklı prompt tekniklerinin (Simple, CoT, Scaffold) performansını karşılaştırır.

**Format:**
```json
{
  "id": "math_001",
  "task_type": "long_multiplication|extraction|json_to_sql|rag_qa",
  "input": {"a": 123, "b": 456},
  "gold": 56088
}
```

## 🚀 Kullanım

1. **UI'dan Upload:**
   - Test Data Management bölümüne gidin
   - "Upload Test Data" butonuna tıklayın
   - İlgili `.jsonl` dosyasını seçin

2. **Test Çalıştırma:**
   - RAG Reliability & Robustness suite'ini seçin
   - İstediğiniz sub-testleri aktifleştirin
   - Upload ettiğiniz data otomatik kullanılır

## 📊 Test Sayıları

- **Faithfulness:** 5 örnek test
- **Context Recall:** 5 örnek test  
- **Answer Relevancy:** 5 örnek test
- **Context Precision:** 5 örnek test (alakasız context'ler dahil)
- **Answer Correctness:** 5 örnek test (faktüel doğruluk)
- **Ground Truth:** 5 örnek test (kapsamlı değerlendirme)
- **Prompt Robustness:** 10 örnek test (4 farklı task type)

## 💡 Özelleştirme

Bu örnekleri kendi use case'inize göre düzenleyebilirsiniz:

- **Kendi domain'iniz:** Finans, sağlık, e-ticaret vb.
- **Kendi context'leriniz:** Ürün dokumanları, FAQ'ler, politikalar
- **Kendi sorularınız:** Müşteri senaryolarına uygun sorular

## 🔧 Validation

Upload etmeden önce JSON formatının doğru olduğundan emin olun:
```bash
cat rag_faithfulness_sample.jsonl | jq .
```

Her satır geçerli JSON objesi olmalı (JSONL format).
