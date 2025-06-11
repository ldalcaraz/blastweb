from flask import Flask, render_template, request, Response, redirect, url_for
import os
import sys
import subprocess
import time
import pwd

app = Flask(__name__, static_url_path='/blast_web/static')
app.config['APPLICATION_ROOT'] = '/blast_web'

# Directorios de trabajo en el clúster
WORK_DIR = "/home/tmp/"
RESULT_DIR = "/home/tmp/"
DB_FOLDER = "/home/tmp/databases"
SOURCE_DB_FOLDER = "/var/www/html/blast_web/databases"

# Rutas explícitas a ejecutables de BLAST
BLAST_BIN = {
    'blastn': '/usr/bin/blastn',
    'blastp': '/usr/bin/blastp',
    'blastx': '/usr/bin/blastx',
    'tblastn': '/usr/bin/tblastn',
    'megablast': '/usr/bin/blastn'
}

@app.route('/')
@app.route('/index')
def index():
    try:
        uid = os.geteuid()
        user = pwd.getpwuid(uid).pw_name
        sys.stderr.write(f"[DEBUG] Usuario efectivo: {user} (UID {uid})\n")

        sys.stderr.write(f"[DEBUG] Leyendo contenido de {DB_FOLDER}\n")
        contents = os.listdir(DB_FOLDER)
        sys.stderr.write(f"[DEBUG] Contenido: {contents}\n")

        db_list = [d for d in contents if os.path.isdir(os.path.join(DB_FOLDER, d))]
        sys.stderr.write(f"[DEBUG] Bases de datos encontradas: {db_list}\n")
    except Exception as e:
        sys.stderr.write(f"[ERROR] No se pudo acceder a {DB_FOLDER}: {str(e)}\n")
        db_list = []

    return render_template("index.html", db_list=db_list)

@app.route('/run_blast', methods=['POST'])
def run_blast():
    blast_type = request.form.get('blast_type')
    database = request.form.get('database')
    sequence = request.form.get('sequence')
    output_format = request.form.get('output_format', '6')

    if not sequence:
        return "Error: No sequence provided", 400

    job_id = str(int(time.time()))
    input_file = f"{WORK_DIR}blast_job_{job_id}.fasta"
    output_file = f"{RESULT_DIR}blast_job_{job_id}.out"
    job_script = f"{WORK_DIR}blast_job_{job_id}.scr"

    with open(input_file, "w") as f:
        f.write(sequence)
    os.chmod(input_file, 0o644)

    db_path = os.path.join(DB_FOLDER, database, database)
    if db_path.endswith('.fasta'):
        db_path = db_path[:-6]

    if not (os.path.exists(db_path + ".nin") or os.path.exists(db_path + ".pin")):
        original_db_path = os.path.join(SOURCE_DB_FOLDER, database)
        if os.path.exists(original_db_path):
            subprocess.run(f"cp -r {original_db_path} {DB_FOLDER}/", shell=True)
        else:
            return f"Error: Database {database} not found", 500

    blast_exe = BLAST_BIN.get(blast_type, '/usr/bin/blastn')

    with open(job_script, "w") as script_file:
        script_file.write(f"""#!/bin/bash
source /etc/profile
source /opt/sge/default/common/settings.sh
{blast_exe} -query {input_file} -db {db_path} -out {output_file} -outfmt {output_format}
chmod 644 {output_file}
""")
    os.chmod(job_script, 0o755)

    try:
        subprocess.run(f"/bin/bash -c 'source /etc/profile && source /opt/sge/default/common/settings.sh && qsub -cwd -j y -S /bin/bash -b y -N blast_{job_id} {job_script}'", shell=True, check=True)
    except subprocess.CalledProcessError as e:
        return f"Error: Failed to submit job {e}", 500

    return redirect(url_for('wait_for_results', job_id=job_id))

@app.route('/wait_for_results/<job_id>')
def wait_for_results(job_id):
    result_url = f"/results/blast_job_{job_id}.out"
    return render_template("results.html", result_url=result_url, job_id=job_id)

@app.route('/results/<filename>')
def get_results(filename):
    result_path = os.path.join(RESULT_DIR, filename)

    if not os.path.exists(result_path):
        return "Result not available yet. Try again later.", 404

    try:
        with open(result_path, 'r') as f:
            blast_output = f.read()
    except Exception as e:
        return f"Error reading result file: {str(e)}", 500

    return Response(blast_output, mimetype='text/plain')

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 - Página no encontrada</h1><p>La URL solicitada no fue encontrada en este servidor.</p>", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')
