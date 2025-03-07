from flask import Flask, render_template, request, Response
import os
import sys
import subprocess
import tempfile

app = Flask(__name__, static_url_path='/blast_web/static')
app.config['APPLICATION_ROOT'] = '/blast_web'

# Path to the databases directory
DB_FOLDER = "/var/www/html/blast_web/databases"

@app.route('/')
@app.route('/index')
def index():
    try:
        # Get only directories inside the database folder
        db_list = [d for d in os.listdir(DB_FOLDER) if os.path.isdir(os.path.join(DB_FOLDER, d))]
        sys.stderr.write(f"[DEBUG] Databases detected: {db_list}\n")
    except Exception as e:
        sys.stderr.write(f"[ERROR] Failed to list databases: {str(e)}\n")
        db_list = []

    return render_template('index.html', db_list=db_list)

@app.route('/run_blast', methods=['POST'])
def run_blast():
    # Get form data
    blast_type = request.form.get('blast_type')
    database = request.form.get('database')
    sequence = request.form.get('sequence')
    output_format = request.form.get('output_format', '6')  # Default to tabular output

    # Debugging logs
    sys.stderr.write(f"[DEBUG] Blast Type: {blast_type}\n")
    sys.stderr.write(f"[DEBUG] Selected Database: {database}\n")
    sys.stderr.write(f"[DEBUG] Selected Output Format: {output_format}\n")

    if not sequence:
        sys.stderr.write("[ERROR] No sequence provided!\n")
        return "Error: No sequence provided", 400

    # Create a temporary file for the input sequence in /tmp/
    input_file = f"/tmp/{next(tempfile._get_candidate_names())}.fasta"
    with open(input_file, "w") as temp_input:
        temp_input.write(sequence)
        temp_input.flush()
        os.fsync(temp_input.fileno())

    os.chmod(input_file, 0o644)

    if not os.path.exists(input_file):
        sys.stderr.write(f"[ERROR] Temporary file was not created: {input_file}\n")
        return f"Error: Temporary file not found ({input_file})", 500

    sys.stderr.write(f"[DEBUG] Created temporary input file: {input_file}\n")

    # Temporary output file
    output_file = f"/tmp/{next(tempfile._get_candidate_names())}.txt"

    # Path to BLAST binary
    BLAST_BIN = {
        'blastn': '/usr/bin/blastn',
        'blastp': '/usr/bin/blastp',
        'blastx': '/usr/bin/blastx',
        'tblastn': '/usr/bin/tblastn',
        'megablast': '/usr/bin/blastn'
    }

    if blast_type not in BLAST_BIN:
        return f"Error: Invalid BLAST type {blast_type}", 400

    # Construct database path and verify index files
    db_path = os.path.join(DB_FOLDER, database, database)
    if db_path.endswith('.fasta'):
        db_path = db_path[:-6]  # Remove .fasta extension
    if not (os.path.exists(db_path + ".nin") or os.path.exists(db_path + ".pin")):
        sys.stderr.write(f"[ERROR] BLAST database not found or improperly formatted: {db_path}\n")
        return f"Error: Database {database} not found or improperly formatted", 400

    cmd = [
        BLAST_BIN[blast_type],
        '-query', input_file,
        '-db', db_path,
        '-out', output_file,
        '-outfmt', output_format
    ]

    if blast_type == 'megablast':
        cmd.append('-task')
        cmd.append('megablast')

    sys.stderr.write(f"[DEBUG] Running command: {' '.join(cmd)}\n")

    try:
        result = subprocess.run(cmd, check=True, capture_output=True, text=True)
        with open(output_file, 'r') as f:
            blast_output = f.read()
        if output_format in ['0', '5']:  # Pairwise or XML formats
            return Response(blast_output, mimetype='text/plain')
    except FileNotFoundError as e:
        sys.stderr.write(f"[ERROR] BLAST binary not found: {e}\n")
        return f"Error: BLAST binary not found: {e}", 500
    except PermissionError as e:
        sys.stderr.write(f"[ERROR] Permission error: {e}\n")
        return f"Error: Permission issue: {e}", 500
    except subprocess.CalledProcessError as e:
        sys.stderr.write(f"[ERROR] BLAST execution failed: {e.stderr}\n")
        return f"Error: BLAST execution failed\n{e.stderr if e.stderr else 'No detailed error available'}", 500
    except Exception as e:
        sys.stderr.write(f"[ERROR] Unexpected error: {e}\n")
        return f"Error: Unexpected error: {e}", 500
    finally:
        os.remove(input_file)
        os.remove(output_file)

    return render_template('results.html', results=blast_output.splitlines())

@app.errorhandler(404)
def page_not_found(e):
    return "<h1>404 - Page Not Found</h1><p>The requested URL was not found on this server.</p>", 404

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0')

