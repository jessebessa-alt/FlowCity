
'use client';
import { useState } from 'react';

export default function ImportarDados() {
  const [fileCrimes, setFileCrimes] = useState(null);
  const [filePop, setFilePop] = useState(null);
  const [status, setStatus] = useState('');
  const [loading, setLoading] = useState(false);

  const handleUpload = async (e) => {
    e.preventDefault();
    if (!fileCrimes || !filePop) {
      setStatus('Por favor, selecione ambos os ficheiros.');
      return;
    }

    setLoading(true);
    setStatus('A enviar ficheiros para o servidor...');

    // Cria o pacote de dados para enviar ao Node.js
    const formData = new FormData();
    formData.append('crimes', fileCrimes);
    formData.append('populacao', filePop);

    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/etl/upload`, {
        method: 'POST',
        body: formData,
      });

      const data = await res.json();
      if (res.ok) {
        setStatus('✅ Sucesso! Os dados foram processados e integrados no mapa.');
      } else {
        setStatus(`❌ Erro: ${data.error}`);
      }
    } catch (err) {
      setStatus('❌ Erro na comunicação com o servidor.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="container" style={{ padding: '2rem', maxWidth: '600px', margin: '0 auto' }}>
      <h1>Motor ETL - Integração de Dados</h1>
      <p>Faça o upload das planilhas para atualizar o banco de dados do mapa.</p>

      <form onSubmit={handleUpload} style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
        <div>
          <label>Planilha de Ocorrências (Crimes):</label>
          <input 
            type="file" 
            accept=".xlsx, .csv" 
            onChange={(e) => setFileCrimes(e.target.files[0])} 
            required 
          />
        </div>

        <div>
          <label>Planilha do Censo (População):</label>
          <input 
            type="file" 
            accept=".xlsx, .csv" 
            onChange={(e) => setFilePop(e.target.files[0])} 
            required 
          />
        </div>

        <button 
          type="submit" 
          disabled={loading}
          style={{ padding: '10px', backgroundColor: '#007bff', color: 'white', border: 'none', borderRadius: '5px' }}
        >
          {loading ? 'A processar no Motor Python...' : 'Iniciar Integração'}
        </button>
      </form>

      {status && <div style={{ marginTop: '1rem', fontWeight: 'bold' }}>{status}</div>}
    </div>
  );
}





