# GitHub Actions ile Otomatik Video Yükleme Kurulumu

Bilgisayarınız kapalıyken bile videolarınızın otomatik üretilip yüklenmesi için bu projeyi GitHub Actions üzerinde çalıştırabilirsiniz. Bu işlem tamamen ücretsizdir.

## Adım 1: GitHub Reposu Oluşturun

1. [GitHub.com](https://github.com) üzerinde yeni bir **Private** repository oluşturun.
2. Proje klasörünüzü bu repoya gönderin:

```bash
git init
git add .
git commit -m "Initial commit"
git branch -M main
git remote add origin https://github.com/KULLANICI_ADINIZ/REPO_ADINIZ.git
git push -u origin main
```

## Adım 2: Secret'ları Ekleyin

1. Reponuzda **Settings** > **Secrets and variables** > **Actions** menüsüne gidin.
2. **New repository secret** butonuna tıklayın ve aşağıdakileri ekleyin:

| Secret Adı | Değer (Dosya İçeriği) |
|------------|---------------------------|
| `PEXELS_API_KEY` | `config.toml` içindeki anahtarınız |
| `CLIENT_SECRET_JSON` | `credentials/motivation_en_client_secret.json` dosyasının tamamı |
| `TOKEN_JSON` | `credentials/motivation_en_token.json` dosyasının tamamı |

## Adım 3: Çalışma Zamanı

Workflow dosyası `.github/workflows/daily_shorts.yml` içinde zamanlama ayarı mevcuttur:
`cron: '0 9,15,21 * * *'` (Günde 3 kez)

## Adım 4: Test

**Actions** sekmesinden workflow'u manuel tetikleyerek test edebilirsiniz.
