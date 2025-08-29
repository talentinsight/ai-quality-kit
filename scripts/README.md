# Requirements Management Scripts

Bu dizin, `requirements.txt` dosyasını otomatik olarak güncellemek için script'ler içerir.

## 📋 Script'ler

### 1. `update_requirements.sh` (Bash Script)
Basit bir bash script'i. Tüm yüklü paketleri `pip freeze` ile alır.

**Kullanım:**
```bash
# Virtual environment'ı aktive et
source .venv/bin/activate

# Script'i çalıştır
./scripts/update_requirements.sh
```

**Özellikler:**
- Virtual environment kontrolü
- Otomatik backup oluşturma
- Eski backup dosyalarını temizleme

### 2. `update_requirements.py` (Python Script) ⭐ **ÖNERİLEN**
Akıllı Python script'i. Sadece ana paketleri kategorilere göre organize eder.

**Kullanım:**
```bash
# Virtual environment'ı aktive et
source .venv/bin/activate

# Script'i çalıştır
python scripts/update_requirements.py
```

**Özellikler:**
- Paketleri kategorilere göre organize eder
- Sadece ana paketleri tutar
- Gereksiz paketleri filtreler
- Otomatik backup oluşturma
- Virtual environment kontrolü

## 🔄 Güncelleme Süreci

### Otomatik Güncelleme (Önerilen)
```bash
# 1. Virtual environment'ı aktive et
source .venv/bin/activate

# 2. Yeni paket yükle
pip install yeni-paket

# 3. Requirements'ı güncelle
python scripts/update_requirements.py
```

### Manuel Güncelleme
```bash
# Tüm paketleri al
pip freeze > requirements.txt

# Veya sadece belirli paketleri
pip freeze | grep -E "(fastapi|uvicorn|pydantic)" > requirements.txt
```

## 📁 Backup Dosyaları

Script'ler otomatik olarak backup oluşturur:
- `requirements.txt.backup.{PID}` - Python script
- `requirements.txt.backup.{YYYYMMDD_HHMMSS}` - Bash script

## ⚠️ Önemli Notlar

1. **Virtual Environment:** Script'leri çalıştırmadan önce `.venv`'yi aktive edin
2. **Backup:** Her güncelleme öncesi otomatik backup oluşturulur
3. **Review:** Güncellenen dosyayı gözden geçirin ve gereksiz paketleri kaldırın
4. **Production:** Production'da sadece gerekli paketleri tutun

## 🎯 Kategoriler

Script, paketleri şu kategorilere göre organize eder:

- **Core FastAPI and web framework**
- **HTTP and async**
- **AI/ML Libraries**
- **Vector search and ML**
- **RAG Evaluation**
- **Database and caching**
- **Authentication and security**
- **Data processing and utilities**
- **Testing and quality**
- **Development tools**
- **Monitoring and observability**
- **Utilities**

## 🚀 Hızlı Başlangıç

```bash
# 1. Script'leri çalıştırılabilir yap
chmod +x scripts/*.sh scripts/*.py

# 2. Virtual environment'ı aktive et
source .venv/bin/activate

# 3. Requirements'ı güncelle
python scripts/update_requirements.py
```

Bu şekilde `requirements.txt` dosyanız her zaman güncel ve organize kalacak! 🎉
