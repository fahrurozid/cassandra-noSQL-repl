from flask import Flask, render_template, request, redirect, url_for
from cassandra.cluster import Cluster
import hvac
import base64
import uuid

# Flask app
app = Flask(__name__)

# Cassandra configuration
cluster = Cluster(['localhost'], port=9042)  
session = cluster.connect()
session.set_keyspace('my_keyspace')  

# Vault configuration
vault_client = hvac.Client(url='http://localhost:8200', token='vault token')  # Ganti dengan token Anda

# Encryption function
def encrypt_data(plaintext):
    plaintext_base64 = base64.b64encode(plaintext.encode('utf-8')).decode('utf-8')
    response = vault_client.secrets.transit.encrypt_data(
        name='encryption-key',
        plaintext=plaintext_base64
    )
    return response['data']['ciphertext']

# Decryption function
def decrypt_data(ciphertext):
    response = vault_client.secrets.transit.decrypt_data(
        name='encryption-key',
        ciphertext=ciphertext
    )
    return base64.b64decode(response['data']['plaintext']).decode('utf-8')

# Insert data into Cassandra
def insert_data_mahasiswa(nim, nama_mahasiswa, jurusan, prodi):
    encrypted_name = encrypt_data(nama_mahasiswa)
    new_id = uuid.uuid4()
    session.execute(
        """
        INSERT INTO data_mahasiswa (id, nim, nama_mahasiswa, jurusan, prodi) 
        VALUES (%s, %s, %s, %s, %s)
        """, (new_id, nim, encrypted_name, jurusan, prodi)
    )

# Fetch data from Cassandra
def fetch_data_mahasiswa():
    rows = session.execute("SELECT id, nim, nama_mahasiswa, jurusan, prodi FROM data_mahasiswa")
    result = []
    for row in rows:
        result.append({
            'id': row.id,
            'nim': row.nim,
            'nama_mahasiswa': decrypt_data(row.nama_mahasiswa),
            'jurusan': row.jurusan,
            'prodi': row.prodi
        })
    return result

# Update data in Cassandra
def update_data_mahasiswa(id, nim, nama_mahasiswa, jurusan, prodi):
    encrypted_name = encrypt_data(nama_mahasiswa)
    session.execute(
        """
        UPDATE data_mahasiswa 
        SET nim=%s, nama_mahasiswa=%s, jurusan=%s, prodi=%s 
        WHERE id=%s
        """, (nim, encrypted_name, jurusan, prodi, uuid.UUID(id))
    )

# Delete data from Cassandra
def delete_data_mahasiswa(id):
    session.execute("DELETE FROM data_mahasiswa WHERE id=%s", (uuid.UUID(id),))

# Routes
@app.route('/')
def index():
    rows = fetch_data_mahasiswa()
    return render_template('index.html', rows=rows)

@app.route('/insert', methods=['POST'])
def insert():
    nim = int(request.form['nim'])
    nama_mahasiswa = request.form['nama_mahasiswa']
    jurusan = request.form['jurusan']
    prodi = request.form['prodi']
    insert_data_mahasiswa(nim, nama_mahasiswa, jurusan, prodi)
    return redirect(url_for('index'))

@app.route('/edit/<id>', methods=['GET'])
def edit(id):
    # Ambil data mahasiswa berdasarkan ID
    row = session.execute("SELECT id, nim, nama_mahasiswa, jurusan, prodi FROM data_mahasiswa WHERE id=%s", (uuid.UUID(id),)).one()
    if row:
        data = {
            'id': row.id,
            'nim': row.nim,
            'nama_mahasiswa': decrypt_data(row.nama_mahasiswa),
            'jurusan': row.jurusan,
            'prodi': row.prodi
        }
        return render_template('edit.html', row=data)
    else:
        return "Data tidak ditemukan", 404

@app.route('/update/<id>', methods=['POST'])
def update(id):
    nim = int(request.form['nim'])
    nama_mahasiswa = request.form['nama_mahasiswa']
    jurusan = request.form['jurusan']
    prodi = request.form['prodi']
    update_data_mahasiswa(id, nim, nama_mahasiswa, jurusan, prodi)
    return redirect(url_for('index'))

@app.route('/delete/<id>', methods=['POST'])
def delete(id):
    delete_data_mahasiswa(id)
    return redirect(url_for('index'))

if __name__ == "__main__":
    app.run(debug=True)
