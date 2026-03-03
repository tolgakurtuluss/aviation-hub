# Flask Avia - Havacılık Veritabanı ve Bilgi Yarışması

Flask Avia, havalimanları ve havayolları hakkında bilgi aramanıza, keşfetmenize ve havacılık bilginizi test etmenize olanak tanıyan bir web uygulamasıdır.

## Özellikler

- **Havalimanı ve Havayolu Arama:** IATA/ICAO kodlarına veya isme göre hızlı arama.
- **Detaylı Bilgi Sayfaları:** Havalimanları ve havayolları için ayrıntılı bilgiler.
- **Coğrafi Keşif:** Ülkelere ve kıtalara göre havalimanlarını ve havayollarını listeleyin.
- **Havacılık Bilgi Yarışması:** IATA kodları, havayolu isimleri ve ülke eşleştirmeleri üzerine eğlenceli bir oyun.

## Kurulum

Bu projeyi yerel makinenizde çalıştırmak için aşağıdaki adımları izleyin.

### Gereksinimler

- Python 3.x
- pip (Python paket yükleyicisi)

### Adımlar

1.  **Projeyi Klonlayın (veya ZIP olarak indirin):**
    ```bash
    git clone https://github.com/kullanici-adiniz/flask-avia.git
    cd flask-avia
    ```

2.  **Sanal Ortam Oluşturun ve Aktive Edin (Önerilir):**
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate

    # macOS / Linux
    python3 -m venv venv
    source venv/bin/activate
    ```

3.  **Gerekli Paketleri Yükleyin:**
    ```bash
    pip install -r requirements.txt
    ```

## Kullanım

### Geliştirme Ortamı

Uygulamayı yerel geliştirme sunucusunda başlatmak için:

```bash
python app.py
```

Uygulama varsayılan olarak `http://127.0.0.1:5000` adresinde çalışacaktır.

**Not:** Bu mod, `debug=True` ayarı ile çalışır ve yalnızca geliştirme amaçlıdır. Prod ortamında kullanılmamalıdır.

### Prod

Uygulamayı bir WSGI sunucusu olan Gunicorn ile çalıştırmak için (macOS/Linux):

```bash
gunicorn --bind 0.0.0.0:8000 app:app
```


## Veri Kaynakları

Bu uygulama, `database/` klasöründe bulunan aşağıdaki Excel dosyalarını kullanır:
- `airportcode.xlsx`
- `carriercode.xlsx`

Tüm veriler uygulama başlangıcında bu dosyalardan okunur ve bellekte saklanır.
