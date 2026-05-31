<div align="center">
    
<a href="https://buymeacoffee.com/abdullaherturk" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/v2/default-yellow.png" alt="Buy Me A Coffee" style="height: 60px !important;width: 217px !important;" ></a>

<img src="https://img.shields.io/badge/Platform-Windows-0078D4?style=for-the-badge&logo=windows&logoColor=white"/>
<img src="https://img.shields.io/badge/Python-3.8+-3776AB?style=for-the-badge&logo=python&logoColor=white"/>
<img src="https://img.shields.io/badge/Flask-Web%20UI-000000?style=for-the-badge&logo=flask&logoColor=white"/>
<img src="https://img.shields.io/badge/iPXE-Network%20Boot-E85D27?style=for-the-badge"/>
<a href="LICENSE"><img src="https://img.shields.io/badge/License-Custom%20%7C%20See%20LICENSE-green?style=for-the-badge"/></a>

![sample](https://github.com/abdullah-erturk/iPXE-Manager/blob/main/preview.jpg)

![sample](https://github.com/abdullah-erturk/iPXE-Manager/blob/main/adminpanel.jpg)

## Download Link:

[![Stable?](https://img.shields.io/badge/Release-v1.svg?style=flat)](https://github.com/abdullah-erturk/iPXE-Manager/archive/refs/heads/main.zip)

# ⚡ iPXE Manager

*Network boot management panel for WinPE, Windows and Linux ISO files over PXE*

*Ağ üzerinden PXE ile WinPE, Windows ve Linux ISO dosyalarını yönetmek için yönetim paneli*

---

<details>
<summary><strong>📋 Değişiklikler / Changelog</strong></summary>

| Version | Changelog |
|--------|------------|
| v1 | İlk Sürüm / First Release |
| v1 fix | Eksik çeviri dil metinleri eklendi / Missing translated language texts have been added. |

</details>
    
[🇹🇷 Türkçe](#türkçe-tanıtım) · [🇬🇧 English](#english-introduction)

</div>

<details>
<summary><strong>🎬 Tanıtım Videoları / Promotional Videos</strong></summary>

<br>
The voiceover is in Turkish. English subtitles can be enabled on YouTube.

Special thanks to **Tayfın AKKOYUN** for his support.

<table>
<tr>
<td align="center" width="50%">
<a href="https://www.youtube.com/watch?v=shk1Y1-UFkQ">
<img src="https://img.youtube.com/vi/shk1Y1-UFkQ/maxresdefault.jpg" alt="iPXE Manager Arayüz Tanıtımı" width="100%">
<br><strong>1. iPXE Manager Arayüz Tanıtımı</strong><br>
<em>Introduction to the iPXE Manager Interface (Features and Usage)</em>
</a>
</td>

<td align="center" width="50%">
<a href="https://www.youtube.com/watch?v=0ym_-8_htto">
<img src="https://img.youtube.com/vi/0ym_-8_htto/maxresdefault.jpg" alt="Windows ISO Entegrasyonu" width="100%">
<br><strong>2. iPXE ile Windows ISO Entegrasyonu ve Kurulumu</strong><br>
<em>Windows ISO Integration and Installation via iPXE</em>
</a>
</td>
</tr>

<tr>
<td align="center" width="50%">
<a href="https://www.youtube.com/watch?v=7Rm8zQ5R_So">
<img src="https://img.youtube.com/vi/7Rm8zQ5R_So/maxresdefault.jpg" alt="Linux ISO Entegrasyonu" width="100%">
<br><strong>3. iPXE ile Linux ISO Entegrasyonu ve Kurulumu</strong><br>
<em>Linux ISO Integration and Installation via iPXE</em>
</a>
</td>

<td align="center" width="50%">
<a href="https://www.youtube.com/watch?v=D7PtqnsExrQ">
<img src="https://img.youtube.com/vi/D7PtqnsExrQ/maxresdefault.jpg" alt="WinPE ISO ve WIM Entegrasyonu" width="100%">
<br><strong>4. iPXE ile WinPE ISO ve WIM Entegrasyonu ve Kurulumu</strong><br>
<em>WinPE ISO and WIM Integration and Installation via iPXE</em>
</a>
</td>
</tr>
</table>

</details>

</div>

## Türkçe Tanıtım

<details>
<summary><strong>📖 Proje Hakkında</strong></summary>

### iPXE Manager Nedir?

iPXE Manager, Windows ve Linux işletim sistemlerini USB veya DVD gibi fiziksel ortamlara gerek kalmadan ağ üzerinden PXE (Preboot eXecution Environment) ile önyüklemenizi sağlayan web tabanlı bir yönetim panelidir.

Bu proje **işyerinde kendi ihtiyaçlarıma göre** geliştirilmiştir. **Ticari bir amacı yoktur** ve bu nedenle **resmi bir destek sağlanmayacaktır**. Başkalarına da faydalı olabileceği düşüncesiyle açık olarak paylaşılmaktadır.

### Kimler Kullanabilir?

**Birincil hedef:** Harici DHCP sunucusu olan kurumsal/şirket ağ ortamları (Windows Server DHCP, pfSense, MikroTik vb.).

**Aynı zamanda:** Ev kullanıcıları — `pxesrv.exe` **ProxyDHCP modunda** çalıştığı için modem veya router yapılandırması gerekmez. Servis, mevcut DHCP sunucunuzla çakışmadan çalışır.

### Teşekkür & Kullanılan Bileşenler

Bu proje iki temel bileşen üzerine inşa edilmiştir:

- **[Erwan'ın TinyPXE Server'ı](http://erwan.labalec.fr/tinypxe/)** — `pxesrv.exe`, temel PXE/TFTP/ProxyDHCP servis motoru olarak kullanılmaktadır. TinyPXE, ücretsiz ancak kapalı kaynak bir uygulamadır.
- **Secure Boot uyumlu iPXE ikili dosyaları** — `ipxe-legacy.pxe` (BIOS), `bootx64.efi` ve `ipxe.efi` (UEFI) olmak üzere önceden derlenmiş iPXE görüntüleridir. iPXE açık kaynaklıdır (GPL). `bootx64.efi` ve `ipxe.efi`, Microsoft tarafından imzalanmıştır; bu sayede çoğu cihazda Secure Boot devre dışı bırakılmadan EFI/BIOS çift önyükleme desteği sağlanır.

</details>

<details>
<summary><strong>✨ Özellikler</strong></summary>

- 🖥️ **Web tabanlı yönetim paneli** — ağdaki herhangi bir cihazdan tarayıcı üzerinden erişilebilir
- 🪟 **Windows ISO desteği** — Windows 10/11/Server ağ kurulumu. Önce WinPE'nin yerel **WebClient** servisi denenir (UNC yolu üzerinden doğrudan WebDAV); kullanılamıyorsa `davinst.exe` **WinFsp** sürücüsünü yükler ve `rclone.exe` ISO'yu sanal sürücü olarak bağlar. **Hem x86 hem x64 WinPE** otomatik desteklenir
- 🐧 **Evrensel Linux desteği** — otomatik distro tespiti ve optimize edilmiş önyükleme parametreleri
- 💾 **WinPE yönetimi** — standart `.wim` dosyaları ve modifiye ISO'lar (örn. Sergei Strelec)
- 🛡️ **Mimari farkındalığı** — UEFI istemcide yalnızca uyumlu (x64) WinPE'ler listelenir; BIOS/Legacy istemcide tüm WinPE'ler görünür
- 🔐 **Şifre koruması** — isteğe bağlı yönetici paneli şifresi (PXE istemcilerini etkilemez)
- 🌍 **Çoklu dil desteği** — `Lang/` klasörüne yeni bir `.ini` dosyası eklemen yeterli; arayüzdeki dil listesi otomatik güncellenir
- 🎨 **Tema desteği** — karanlık/aydınlık mod
- 📊 **Canlı kontrol paneli** — sunucu durumu, aktif bağlantılar, ISO istatistikleri
- 🔧 **DHCP/Güvenlik Duvarı araçları** — Windows DHCP Sunucusu için tek tıklama policy oluşturucu
- 🔄 **Otomatik iPXE script üretimi** — herhangi bir değişiklikte önyükleme menüsü anında güncellenir
- 📋 **Unattend XML desteği** — otomatik Windows kurulumu için yanıt dosyası
- ⏱️ **Önyükleme geri sayımı** — varsayılan önyükleme seçeneğiyle yapılandırılabilir zaman aşımı
- 🗂️ **ISO içerik tarayıcısı** — yüklenen ISO dosyalarının iç yapısını panelden inceleme
- 📜 **Extract log görüntüleyici** — uzun süren ISO/WinPE ayıklama işlemlerinin günlüğünü canlı izleme
- ↕️ **Sürükle-bırak ile sıralama** — önyükleme menüsündeki öğelerin sırasını panelden değiştirme
- ✏️ **Açıklama (alias) düzenleme** — her ISO/WinPE için kullanıcı dostu görünen ad atama
- 🛡️ **Windows 11 bypass** — kayıt defteri üzerinden otomatik TPM/Secure Boot/RAM gereksinim atlatma
- 📦 **Servis modu** — otomatik başlatma için Windows servisi olarak kurulum
- 🛑 **Güvenli kapatma** — sistemi ve tüm arka plan servislerini panelden tek tıkla durdurma
- 💾 **Kalıcı ayarlar** — Ayarları Kaydet butonu; sunucu IP/domain, arayüz dili, tema (karanlık/aydınlık), varsayılan önyükleme hedefi ve geri sayım süresini `app_settings.json` dosyasına kaydeder; ardından tüm Linux ISO'ları yeniden tarar ve iPXE önyükleme menüsünü otomatik yeniden üretir

> 💡 **Yeni dil eklemek için:** `Lang/` klasöründeki `English.ini` dosyasını kopyalayın, bölüm adını ve değerleri çevirin. Başka hiçbir dosyaya dokunmanıza gerek yoktur.

</details>

<details>
<summary><strong>🐧 Evrensel Linux Desteği</strong></summary>

iPXE Manager, Linux dağıtımını ISO yapısından (dosya adından değil) otomatik olarak tespit eder ve doğru önyükleme yöntemini uygular.

### Distro Bazlı Tespit ve Önyükleme Yöntemi

| Dağıtım | Tespit Yöntemi | Önyükleme Yöntemi | RAM Kullanımı | Durum |
|---|---|---|---|---|
| Ubuntu / Mint / Zorin / Pop!_OS (Tüm Sürümler) | `casper/` veya katmanlı `squashfs` | `url=` tam ISO (HTTP üzerinden ISO bağlama) | Değişken (ISO Boyutuna Göre) | ✅ Tam |
| Debian / Kali / MX / Parrot / antiX | `live/filesystem.squashfs` | `fetch=` tek squashfs | ~3–5 GB | ✅ Tam |
| Fedora / Rocky / Alma / CentOS Stream | `LiveOS/squashfs.img` | `root=live:` squashfs | ~2–4 GB | ✅ Tam |
| openSUSE Live | `LiveOS/squashfs.img` | `root=live:` squashfs | ~3–4 GB | ✅ Tam |
| openSUSE Installer | squashfs yok (kurulum) | `install=http://` (sıfır RAM) | ~256 MB | ✅ Tam |
| Arch Linux / EndeavourOS | `arch/` dizini | `archiso_http_srv=` | ~1–2 GB | ✅ Tam |
| Manjaro | `manjaro/` dizini | `archiso_http_srv=` + dinamik `img_loop` | ~2–3 GB | ✅ Tam |
| Alpine Linux (LTS/Extended/Edge) | `alpine-release` / `modloop-*` | `modloop=` (dinamik yol) | ~256 MB | ✅ Tam |
| Void Linux | `boot/vmlinuz` + `LiveOS/` | `root=live:` squashfs | ~1–2 GB | ✅ Tam |
| NixOS | `nix-store/` + grub.cfg parse | `init=` (grub.cfg'den ayrıştırılır) | ~2–3 GB | ⚠️ Kısmi |
| Generic / Bilinmeyen | En büyük squashfs taraması | `root=live:` veya tam ISO fallback | Değişken | ⚠️ Kısmi |
| Tails / Whonix | Özel şifreli live yapısı | — | — | ❌ Yok |
| Gentoo / Slackware | Standart live formatı yok | — | — | ❌ Yok |

> **\* Ubuntu notu:** Canonical'ın son sürümlerde (özellikle 22.04 ve 24.04+) geçiş yaptığı yeni Subiquity ve çok katmanlı (layered) squashfs mimarilerinde eski `fetch=` yöntemi RAM dolması veya "Unable to find a medium" hatalarına neden olduğu için; iPXE Manager tüm Ubuntu tabanlı sistemlerde artık en modern ve stabil yöntem olan `url=` (Tam ISO bağlama) metodunu kullanmaktadır.

> **⚠️ Secure Boot:** Linux PXE önyüklemesi için UEFI ayarlarından Secure Boot'un **devre dışı** bırakılması gerekmektedir.

### Squashfs Yolu Tespiti

Gömülü PowerShell betik dosyası (`extract_iso.ps1`) otomatik olarak:
1. ISO'yu mount eder
2. Dizin yapısından distro'yu tespit eder
3. Bilinen yolları tarayarak doğru squashfs/modloop dosyasını bulur
4. Gerçek yolu `squashfs_path.txt`'e kaydeder
5. Kernel (`vmlinuz`) ve initrd'yi diske kopyalar

Tüm önyükleme parametreleri bu hint dosyalarından dinamik olarak üretilir — hardcoded yol yoktur.

**Genel Linux kapsamı: Yaygın kullanılan dağıtımların indirme hacmine göre yaklaşık %88'i**

</details>

<details>
<summary><strong>🚀 Başlangıç</strong></summary>

### Gereksinimler

- Windows 10/11 veya Windows Server 2016+
- Python 3.8+ (kaynak koddan çalıştırılıyorsa) veya derlenmiş `.exe`
- Yönetici (Administrator) yetkileri — ISO mount, boot.wim düzenleme ve servis yönetimi için gerekli
- PXE istemcileriyle aynı alt ağda bir ağ arayüzü

### Kurulum

1. Uygulama klasörünü herhangi bir konuma çıkarın (örn. `D:\iPXE Manager`)
2. `iPXE Manager.exe`'yi **Yönetici olarak çalıştırın**
3. `http://localhost:8080` adresinden web paneline erişin
4. **Sunucu IP / Domain** alanı, çalıştığı bilgisayarın IP adresiyle otomatik olarak doldurulur. Bir domain adı kullanmak veya farklı bir ağ arayüzünün IP'sini belirtmek istiyorsanız değiştirip **Ayarları Kaydet**'e tıklayın
5. **PXE Servisini** başlatın

### Ev Kullanıcıları İçin (Router Yapılandırması Gerekmez)

`pxesrv.exe`, varsayılan olarak **ProxyDHCP modunda** çalışır (`config.ini` dosyasında `proxydhcp=1`):

- Modem/router'ınız IP adresi atamaya normal şekilde devam eder
- `pxesrv.exe` yalnızca PXE önyükleme isteklerine önyükleme dosyası bilgisiyle yanıt verir
- Router yapılandırması gerekmez — servisi başlatın ve istemcinizi önyükleyin

### Kurumsal Ağlar İçin (Harici DHCP Sunucusu)

Yerleşik **DHCP / Güvenlik Duvarı Yapılandırması** panelini kullanın:

1. Sunucu IP/domain adresini doğrulayın (otomatik doldurulur — gerekiyorsa düzeltin)
2. **Konfigürasyon Dosyasını İndir (.BAT)** butonuna tıklayın
3. `.bat` dosyasını **Windows DHCP Sunucunuzda** Yönetici olarak çalıştırın
4. EFI ve BIOS istemciler için otomatik olarak iPXE önyükleme policy'si oluşturulur

</details>

<details>
<summary><strong>📁 Dizin Yapısı</strong></summary>

```
iPXE Manager/
├── iPXE Manager.exe
├── index.html
├── LICENSE.txt
├── README.md
├── Lang/
│   ├── English.ini
│   ├── Turkish.ini
│   └── <Dil>.ini               ← Yeni dil eklemek için bu şablonu kopyalayın
├── Source Codes/
│   ├── iPXE Manager_source.py  ← Sunucu kaynak kodu (Python/Flask)
│   └── davinst_source.py       ← WinPE WebDAV servis yükleyici kaynağı (x86 ve x64 için ayrı derlenir)
└── pxe/
    ├── pxesrv.exe              ← TinyPXE Server (Erwan tarafından)
    ├── config.ini              ← pxesrv yapılandırması
    ├── autoexec.ipxe           ← iPXE önyükleme menüsü (otomatik oluşturulur)
    ├── bootx64.efi             ← UEFI Secure Boot önyükleyici (MS imzalı)
    ├── ipxe-legacy.pxe         ← BIOS önyükleme dosyası
    ├── ipxe.efi                ← UEFI iPXE çalışma zamanı (iPXE imzalı)
    ├── app_settings.json       ← Uygulama ayarları (otomatik oluşturulur)
    ├── ISO/
    │   ├── Windows/            ← Windows ISO klasörleri
    │   └── Linux/              ← Linux ISO klasörleri
    ├── WINPE/                  ← WinPE .wim ve modifiye WinPE ISO dosyaları
    └── TOOLS/
        ├── wimlib-imagex.exe   ← WIM düzenleme aracı (Windows ISO için boot.wim'e dosya enjekte eder)
        ├── libwim-15.dll       ← wimlib-imagex bağımlılığı
        └── MS/
            ├── boot.sdi
            ├── bootmgr.exe
            ├── wimboot
            ├── boot/bcd            ← BIOS BCD
            ├── efi/microsoft/boot/ ← EFI BCD
            ├── dynamic/            ← Otomatik üretilen WinSetup betikleri
            └── rclone/                ← Windows ISO kurulum bileşenleri (WinFsp+RClone fallback yolu)
                ├── rclone_amd64.exe   ← x64 rclone (WebDAV→sanal sürücü bağlantısı)
                ├── rclone_x86.exe     ← x86 rclone (x86 WinPE için)
                ├── davinst_amd64.exe  ← x64 WinPE'de WinFsp sürücüsünü yükler
                ├── davinst_x86.exe    ← x86 WinPE'de WinFsp sürücüsünü yükler
                ├── winfsp-x64.sys     ← WinFsp sanal dosya sistemi sürücüsü (x64)
                ├── winfsp-x86.sys     ← WinFsp sanal dosya sistemi sürücüsü (x86)
                ├── winfsp-x64.dll     ← WinFsp kullanıcı modu kütüphanesi (x64)
                ├── winfsp-x86.dll     ← WinFsp kullanıcı modu kütüphanesi (x86)
                ├── ucrt_x64/          ← x64 WinPE'ye enjekte edilen UCRT/API Set DLL'leri
                └── ucrt_x86/          ← x86 WinPE'ye enjekte edilen UCRT/API Set DLL'leri
```

</details>

<details>
<summary><strong>⚠️ Önemli Notlar ve Sınırlamalar</strong></summary>

- **Yalnızca Windows** — uygulama, `Mount-DiskImage` (PowerShell) ve diğer Windows'a özgü API'leri kullanır
- **Windows ISO → WebClient (öncelikli) / RClone + WinFsp (yedek)** — Önce WinPE'nin yerel **WebClient** servisi başlatılarak doğrudan WebDAV UNC yolu (`\\SERVER@PORT\DavWWWRoot\dav\ISO_DIR`) üzerinden bağlantı denenir. WinPE'de WebClient mevcut değilse veya başarısız olursa `davinst.exe` **WinFsp** sürücüsünü yükler ve `rclone.exe` ISO içeriğini sanal sürücü olarak bağlar. Her iki yöntemde de Windows Setup, ISO dosyalarına yerel sürücüymüş gibi erişir; SMB paylaşımı veya ek kullanıcı hesabı gerekmez. **x86 ve x64 WinPE** otomatik desteklenir (mimari otomatik tespit edilir, ilgili ikili dosyalar enjekte edilir)
- **Yönetici yetkisi gerekli** — ISO mount, `wimlib-imagex` ile boot.wim düzenleme ve servis yönetimi yükseltilmiş ayrıcalıklar gerektirir
- **ISO dosyaları kalıcı olarak mount edilmiş kalır** — Modifiye WinPE, Windows Setup ve Linux ISO dosyaları, sunucu çalıştığı sürece Windows tarafından sanal sürücü olarak mount edilmiş halde tutulur. Bunun nedeni; istemci her dosyaya (squashfs, boot.wim, kernel vb.) eriştiğinde sunucunun ISO içeriğini anlık olarak HTTP veya WebDAV üzerinden okuyup servis etmesidir. ISO unmount edilirse istemci bağlantısı kesilir ve önyükleme başarısız olur. Uygulama kapatıldığında tüm mount işlemleri otomatik olarak sonlandırılır; yeniden açıldığında ise mevcut ISO dosyaları otomatik olarak tekrar mount edilir.
- **Sürücü harfleri** — her mount edilen ISO bir Windows sürücü harfi (A–Z) tüketir; tipik kullanımda pratik bir sorun değildir
- **Linux RAM gereksinimleri** — Linux destek tablosuna bakın; Ubuntu 24.04+ önemli miktarda RAM gerektirir
- **Linux için Secure Boot yok** — Linux PXE önyüklemesi için Secure Boot devre dışı bırakılmalıdır; Windows önyüklemesi imzalı iPXE EFI ile Secure Boot etkin çalışır
- **Ticari destek yok** — bu proje kişisel işyeri kullanımı için geliştirilmiştir; sorunlar bildirilebilir ancak yanıt garanti edilmez

</details>

<details>
<summary><strong>📜 Lisans ve Feragatname — <a href="LICENSE">LICENSE dosyasını görüntüle</a></strong></summary>

Bu proje **Abdullah ERTÜRK** tarafından kişisel işyeri kullanımı için geliştirilmiştir. Ticari bir amacı yoktur.

> 📄 Tam lisans metni için: [LICENSE](LICENSE)

- Ticari olmayan amaçlarla kullanım, değiştirme ve paylaşım serbesttir
- **Atıf zorunludur** — kaynak kodda ve arayüzde yazar adı ile linkleri korunmalıdır
- Hiçbir türde garanti sağlanmamaktadır
- Resmi destek sunulmamaktadır
- Üçüncü taraf bileşenler (pxesrv, iPXE ikili dosyaları) kendi lisanslarına tabidir

**Bağlantılar:**
- 🌐 [erturk-dev.netlify.app](https://erturk-dev.netlify.app)
- 💻 [github.com/abdullah-erturk](https://github.com/abdullah-erturk)
- 🔧 [Erwan'ın TinyPXE'si](http://erwan.labalec.fr/tinypxe/)
- ⚡ [iPXE — github.com/ipxe/ipxe](https://github.com/ipxe/ipxe)

</details>

---

## English Introduction

<details>
<summary><strong>📖 About the Project</strong></summary>

### What is iPXE Manager?

iPXE Manager is a web-based management panel that allows you to boot Windows and Linux operating systems over the network via PXE (Preboot eXecution Environment), without requiring any physical media such as USB drives or DVDs.

This project was developed for **workplace needs**. It has **no commercial purpose**, and therefore **no official support will be provided**. It is shared openly in the hope that it may be useful to others.

### Who Is It For?

**Primary target:** Corporate/enterprise network environments with an external DHCP server (Windows Server DHCP, pfSense, MikroTik, etc.).

**Also works for:** Home users — thanks to `pxesrv.exe` running in **ProxyDHCP mode**, no router or modem configuration is required. The service runs alongside your existing DHCP server without conflict.

### Credits & Acknowledgements

This project builds on two key components:

- **[Erwan's TinyPXE Server](http://erwan.labalec.fr/tinypxe/)** — `pxesrv.exe` is used as the underlying PXE/TFTP/ProxyDHCP service engine. TinyPXE is freeware but closed source.
- **Secure Boot–compatible iPXE binaries** — `ipxe-legacy.pxe` (BIOS), `bootx64.efi` and `ipxe.efi` (UEFI) are pre-built iPXE images. iPXE is open source (GPL). `bootx64.efi` and `ipxe.efi` are signed by Microsoft, enabling EFI/BIOS dual boot without disabling Secure Boot on most devices.

</details>

<details>
<summary><strong>✨ Features</strong></summary>

- 🖥️ **Web-based management panel** — browser-accessible from any device on the network
- 🪟 **Windows ISO support** — network installation of Windows 10/11/Server. WinPE's native **WebClient** service is tried first (direct WebDAV via UNC path); if unavailable, `davinst.exe` loads the **WinFsp** driver and `rclone.exe` mounts the ISO as a virtual drive. **Both x86 and x64 WinPE** are auto-supported
- 🐧 **Universal Linux support** — automatic distro detection and optimized boot parameters
- 💾 **WinPE management** — standard `.wim` files and modified ISOs (e.g. Sergei Strelec)
- 🛡️ **Architecture awareness** — UEFI clients only see compatible (x64) WinPE entries; BIOS/Legacy clients see all entries
- 🔐 **Password protection** — optional admin panel password (does not affect PXE clients)
- 🌍 **Multi-language support** — drop a new `.ini` into the `Lang/` folder; the interface language list updates automatically
- 🎨 **Theme support** — dark/light mode
- 📊 **Live dashboard** — server status, active connections, ISO statistics
- 🔧 **DHCP/Firewall tools** — one-click policy generator for Windows DHCP Server
- 🔄 **Automatic iPXE script generation** — boot menu updates instantly on any change
- 📋 **Unattend XML support** — automated Windows installation answer files
- ⏱️ **Boot countdown** — configurable timeout with default boot option
- 🗂️ **ISO content browser** — inspect the internal structure of uploaded ISO files from the panel
- 📜 **Extract log viewer** — watch the live log of long-running ISO/WinPE extraction tasks
- ↕️ **Drag-and-drop reordering** — rearrange boot menu items directly from the panel
- ✏️ **Description (alias) editing** — assign a friendly display name to each ISO/WinPE entry
- 🛡️ **Windows 11 bypass** — automatic TPM/Secure Boot/RAM requirement bypass via registry
- 📦 **Service mode** — install as Windows service for automatic startup
- 🛑 **Safe shutdown** — stop the system and all background services from the panel with a single click
- 💾 **Persistent settings** — the Save Settings button writes server IP/domain, interface language, theme (dark/light), default boot target, and countdown duration to `app_settings.json`; it then re-scans all Linux ISOs and regenerates the iPXE boot menu automatically

> 💡 **To add a new language:** Copy `English.ini` from the `Lang/` folder, translate the section name and values. No other files need to be modified.

</details>

<details>
<summary><strong>🐧 Linux Universal Support</strong></summary>

iPXE Manager automatically detects the Linux distribution from the ISO structure (not the filename) and applies the correct boot method.

### Detection & Boot Method by Distro

| Distribution | Detection Method | Boot Method | RAM Usage | Status |
|---|---|---|---|---|
| Ubuntu / Mint / Zorin / Pop!_OS (All Versions) | `casper/` or layered `squashfs` | `url=` full ISO (HTTP loop mount) | Varies (By ISO Size) | ✅ Full |
| Debian / Kali / MX / Parrot / antiX | `live/filesystem.squashfs` | `fetch=` single squashfs | ~3–5 GB | ✅ Full |
| Fedora / Rocky / Alma / CentOS Stream | `LiveOS/squashfs.img` | `root=live:` squashfs | ~2–4 GB | ✅ Full |
| openSUSE Live | `LiveOS/squashfs.img` | `root=live:` squashfs | ~3–4 GB | ✅ Full |
| openSUSE Installer | No squashfs (installer) | `install=http://` (zero RAM overhead) | ~256 MB | ✅ Full |
| Arch Linux / EndeavourOS | `arch/` directory | `archiso_http_srv=` | ~1–2 GB | ✅ Full |
| Manjaro | `manjaro/` directory | `archiso_http_srv=` + dynamic `img_loop` | ~2–3 GB | ✅ Full |
| Alpine Linux (LTS/Extended/Edge) | `alpine-release` / `modloop-*` | `modloop=` (dynamic path) | ~256 MB | ✅ Full |
| Void Linux | `boot/vmlinuz` + `LiveOS/` | `root=live:` squashfs | ~1–2 GB | ✅ Full |
| NixOS | `nix-store/` + grub.cfg parse | `init=` (parsed from grub.cfg) | ~2–3 GB | ⚠️ Partial |
| Generic / Unknown | Largest squashfs scan | `root=live:` or full ISO fallback | Varies | ⚠️ Partial |
| Tails / Whonix | Special encrypted live | — | — | ❌ No |
| Gentoo / Slackware | No standard live format | — | — | ❌ No |

> **\* Ubuntu note:** Due to Canonical's transition to Subiquity and layered squashfs architectures in recent versions (especially 22.04 and 24.04+), the legacy `fetch=` parameter often causes RAM overflow or "Unable to find a medium" errors. Therefore, iPXE Manager now uses the modern, most stable `url=` (Full ISO) method for all Ubuntu-based systems.

> **⚠️ Secure Boot:** Linux PXE boot requires Secure Boot to be **disabled** in UEFI settings.

### Squashfs Path Detection

The embedded PowerShell script file (`extract_iso.ps1`) automatically:
1. Mounts the ISO
2. Detects the distro from directory structure
3. Finds the correct squashfs/modloop file by scanning known paths
4. Saves the real path to `squashfs_path.txt`
5. Copies kernel (`vmlinuz`) and initrd to disk

All boot parameters are generated dynamically from these hint files — no hardcoded paths.

**Overall Linux coverage: ~88% of commonly distributed distros (by download volume)**

</details>

<details>
<summary><strong>🚀 Getting Started</strong></summary>

### Requirements

- Windows 10/11 or Windows Server 2016+
- Python 3.8+ (if running from source) or the compiled `.exe`
- Administrator privileges (required for ISO mount, boot.wim patching, and service management)
- Network interface on the same subnet as PXE clients

### Installation

1. Extract the application folder to any path (e.g. `D:\iPXE Manager`)
2. Run `iPXE Manager.exe` as **Administrator**
3. Open the web panel at `http://localhost:8080`
4. The **Server IP / Domain** field is auto-detected from the host machine's IP. To use a domain name or a different network interface IP, change it and click **Save Settings**
5. Start the **PXE Service**

### For Home Users (No Router Config Needed)

`pxesrv.exe` runs in **ProxyDHCP mode** (`proxydhcp=1` in `config.ini`) by default:

- Your router/modem continues to assign IP addresses normally
- `pxesrv.exe` only responds to PXE boot requests with boot file information
- No router configuration required — just start the service and boot your client

### For Enterprise Networks (External DHCP Server)

Use the built-in **DHCP / Firewall Configuration** panel:

1. Verify the server IP/domain (auto-filled — adjust if needed)
2. Click **Download Configuration File (.BAT)**
3. Run the `.bat` file as Administrator on your **Windows DHCP Server**
4. This creates an iPXE boot policy automatically for EFI and BIOS clients

</details>

<details>
<summary><strong>📁 Directory Structure</strong></summary>

```
iPXE Manager/
├── iPXE Manager.exe
├── index.html
├── LICENSE.txt
├── README.md
├── Lang/
│   ├── English.ini
│   ├── Turkish.ini
│   └── <Language>.ini          ← Copy this template to add a new language
├── Source Codes/
│   ├── iPXE Manager_source.py  ← Server source code (Python/Flask)
│   └── davinst_source.py       ← WinPE WebDAV service installer source (compiled separately for x86 and x64)
└── pxe/
    ├── pxesrv.exe              ← TinyPXE Server (by Erwan)
    ├── config.ini              ← pxesrv configuration
    ├── autoexec.ipxe           ← iPXE boot menu (auto-generated)
    ├── bootx64.efi             ← UEFI Secure Boot bootloader (MS signed)
    ├── ipxe-legacy.pxe         ← BIOS boot file
    ├── ipxe.efi                ← UEFI iPXE runtime (iPXE signed)
    ├── app_settings.json       ← Application settings (auto-generated)
    ├── ISO/
    │   ├── Windows/            ← Windows ISO folders
    │   └── Linux/              ← Linux ISO folders
    ├── WINPE/                  ← WinPE .wim and modified WinPE ISO files
    └── TOOLS/
        ├── wimlib-imagex.exe   ← WIM manipulation tool (injects files into boot.wim for Windows ISO)
        ├── libwim-15.dll       ← wimlib-imagex dependency
        └── MS/
            ├── boot.sdi
            ├── bootmgr.exe
            ├── wimboot
            ├── boot/bcd            ← BIOS BCD
            ├── efi/microsoft/boot/ ← EFI BCD
            ├── dynamic/            ← Auto-generated WinSetup scripts
            └── rclone/                ← Windows ISO installation components (WinFsp+RClone fallback path)
                ├── rclone_amd64.exe   ← x64 rclone (mounts WebDAV share as virtual drive)
                ├── rclone_x86.exe     ← x86 rclone (for x86 WinPE)
                ├── davinst_amd64.exe  ← loads WinFsp driver in x64 WinPE
                ├── davinst_x86.exe    ← loads WinFsp driver in x86 WinPE
                ├── winfsp-x64.sys     ← WinFsp filesystem driver (x64)
                ├── winfsp-x86.sys     ← WinFsp filesystem driver (x86)
                ├── winfsp-x64.dll     ← WinFsp user-mode library (x64)
                ├── winfsp-x86.dll     ← WinFsp user-mode library (x86)
                ├── ucrt_x64/          ← UCRT/API Set DLLs injected into x64 WinPE
                └── ucrt_x86/          ← UCRT/API Set DLLs injected into x86 WinPE
```

</details>

<details>
<summary><strong>⚠️ Important Notes & Limitations</strong></summary>

- **Windows only** — the application uses `Mount-DiskImage` (PowerShell) and other Windows-specific APIs
- **Windows ISO → WebClient (preferred) / RClone + WinFsp (fallback)** — WinPE's native **WebClient** service is started first and the WebDAV UNC path (`\\SERVER@PORT\DavWWWRoot\dav\ISO_DIR`) is mounted directly. If WebClient is unavailable or fails, `davinst.exe` loads the **WinFsp** virtual filesystem driver and `rclone.exe` exposes the WebDAV share as a local drive letter. Either way, Windows Setup accesses the installation files as if from a local drive; no SMB share or extra user account is required. **Both x86 and x64 WinPE** are auto-supported (architecture is detected and the corresponding binaries are injected)
- **Administrator required** — ISO mounting, `wimlib-imagex` boot.wim patching, and service management need elevated privileges
- **ISOs remain permanently mounted** — Modified WinPE, Windows Setup, and Linux ISO files are kept mounted as virtual drives by Windows for as long as the server is running. This is required because every time a client requests a file (squashfs, boot.wim, kernel, etc.), the server reads directly from the mounted ISO and serves it instantly over HTTP or WebDAV. If an ISO were unmounted while a client is booting, the connection would be lost and the boot would fail. All ISOs are automatically unmounted when the application is closed and automatically remounted when it is reopened.
- **Drive letters** — each mounted ISO consumes a Windows drive letter (A–Z limit); practically not an issue for typical deployments
- **Linux RAM requirements** — see the Linux support table; Ubuntu 24.04+ requires significant RAM
- **No Secure Boot for Linux** — Linux PXE boot requires Secure Boot disabled; Windows boot works with Secure Boot enabled (signed iPXE EFI)
- **No commercial support** — this project was built for personal workplace use; issues are welcome but responses are not guaranteed

</details>

<details>
<summary><strong>📜 License & Disclaimer — <a href="LICENSE">View LICENSE file</a></strong></summary>

This project was developed by **Abdullah ERTÜRK** for personal workplace use. It has no commercial purpose.

> 📄 Full license text: [LICENSE](LICENSE)

- Free to use, modify, and share for non-commercial purposes
- **Attribution required** — author name and links must be preserved in source code and UI
- No warranty of any kind is provided
- Official support is not available
- Third-party components (pxesrv, iPXE binaries) are subject to their own licenses

**Links:**
- 🌐 [erturk-dev.netlify.app](https://erturk-dev.netlify.app)
- 💻 [github.com/abdullah-erturk](https://github.com/abdullah-erturk)
- 🔧 [Erwan's TinyPXE](http://erwan.labalec.fr/tinypxe/)
- ⚡ [iPXE — github.com/ipxe/ipxe](https://github.com/ipxe/ipxe)

</details>

---

<div align="center">

<p align="center">
  <b>Developed by Abdullah ERTÜRK</b><br>
  <a href="https://erturk-dev.netlify.app" target="_blank">erturk-dev.netlify.app</a> | <a href="https://github.com/abdullah-erturk" target="_blank">github.com/abdullah-erturk</a>
</p>
