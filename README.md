
# Interfaz Web para correr blast en un sistema de colas SGE
## 1. Instalación de paquetes necesarios

```bash
sudo apt update
sudo apt install -y \
    python3-venv \
    python3-dev \
    apache2 \
    libapache2-mod-wsgi-py3 \
    gridengine-client \
    gridengine-master \
    gridengine-exec \
    letsencrypt \
    sudo \
    rsync
```

## 2. Configuración del entorno

Editar el archivo `/etc/environment` para que Grid Engine funcione al enviar trabajos desde Apache:

```bash
sudo nano /etc/environment
```

Agregar o modificar las siguientes variables:

```bash
SGE_ROOT=/opt/sge
SGE_CELL=deep-thought
```

Luego cerrar sesión y volver a entrar, o usar `source /etc/environment`.

## 3. Configuración del entorno virtual de Flask

```bash
cd /var/www/html/blast_web
python3 -m venv venv
source venv/bin/activate
pip install flask
```

## 4. Configuración de Apache con Flask y WSGI

### Archivo `/etc/apache2/sites-available/000-default-le-ssl.conf`:

```apache
<IfModule mod_ssl.c>
<VirtualHost *:443>
    ServerAdmin webmaster@localhost
    ServerName *****

    SSLEngine on
    SSLCertificateFile /etc/letsencrypt/live/*****/fullchain.pem
    SSLCertificateKeyFile /etc/letsencrypt/live/*****/privkey.pem
    Include /etc/letsencrypt/options-ssl-apache.conf

    DocumentRoot /var/www/html
    <Directory /var/www/html>
        AllowOverride All
        Require all granted
        <FilesMatch \.php$>
            SetHandler "proxy:unix:/run/php/php8.4-fpm.sock|fcgi://localhost/"
        </FilesMatch>
    </Directory>

    Alias /ganglia /usr/share/ganglia-webfrontend
    <Directory /usr/share/ganglia-webfrontend>
        AllowOverride All
        Require all granted
        <FilesMatch \.php$>
            SetHandler "proxy:unix:/run/php/php7.4-fpm.sock|fcgi://localhost/"
        </FilesMatch>
    </Directory>

    WSGIDaemonProcess flask_blast_https user=worker group=genomica threads=4 python-home=/var/www/html/blast_web/venv
    WSGIScriptAlias /blast_web /var/www/html/blast_web/wsgi.py

    <Directory /var/www/html/blast_web>
        Require all granted
        WSGIProcessGroup flask_blast_https
        WSGIApplicationGroup %{GLOBAL}
    </Directory>

    Alias /blast_web/static /var/www/html/blast_web/static
    <Directory /var/www/html/blast_web/static>
        Require all granted
    </Directory>

    Alias /results /home/tmp/
    <Directory /home/tmp/>
        Require all granted
    </Directory>

    ErrorLog ${APACHE_LOG_DIR}/flask_blast_ssl_error.log
    CustomLog ${APACHE_LOG_DIR}/flask_blast_ssl_access.log combined
</VirtualHost>
</IfModule>
```

### Habilitar módulos Apache necesarios

```bash
sudo a2enmod alias
sudo a2enmod wsgi
sudo systemctl restart apache2
```

## 5. Configuración del usuario para Grid Engine

```bash
sudo qconf -au worker
```

## 6. Preparación de bases de datos BLAST

```bash
mkdir -p /var/www/html/blast_web/databases/MiBase
makeblastdb -in secuencias.fasta -dbtype nucl -out /var/www/html/blast_web/databases/MiBase/MiBase
```

Permisos:

```bash
sudo chown -R www-data:genomica /var/www/html/blast_web/databases/MiBase
sudo chmod -R 755 /var/www/html/blast_web/databases/MiBase
```

## 7. Configuración del `wsgi.py`

```python
import sys
import os

sys.path.insert(0, "/var/www/html/blast_web")
from app import app as application
```

## 8. Habilitación de HTTPS

```bash
sudo certbot --apache
```

## 9. Reinicio del servidor

```bash
sudo systemctl restart apache2
```

## 10. Acceso al servidor

- Interfaz BLAST: https://*****/blast_web/
- WordPress: https://*****/
- Ganglia: https://*****/ganglia/
