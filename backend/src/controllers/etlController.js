import { exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import os from 'os'; // Adicionado para detetar o sistema operativo (Windows ou Linux)
import { fileURLToPath } from 'url';

// Recria o __dirname que não existe por padrão em ES Modules (import)[cite: 7]
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const processarETL = (req, res) => {
  // 1. Verifica se os ficheiros chegaram[cite: 7]
  if (!req.files || !req.files.crimes || !req.files.populacao) {
    return res.status(400).json({ error: 'Os dois ficheiros são obrigatórios.' });
  }

  // Pega os caminhos temporários onde o Multer guardou os ficheiros[cite: 7]
  const caminhoCrimes = req.files.crimes[0].path;
  const caminhoPop = req.files.populacao[0].path;
  const caminhoSQL = path.join(__dirname, '../../uploads/saida_motor.sql');

  // Onde o seu script Python está guardado no backend[cite: 7]
  const scriptPython = path.join(__dirname, '../../scripts/gerar_banco_app.py');

  // 2. Caminho dinâmico para o executável do Python DENTRO do .venv
  const isWindows = os.platform() === 'win32';
  
  // Caminho assumindo que o .venv foi criado na raiz do backend (onde fica o package.json)
  const venvPath = path.join(__dirname, '../../.venv'); 
  
  const pythonExecutable = isWindows 
    ? path.join(venvPath, 'Scripts', 'python.exe') // Caminho se estiver a testar no Windows local
    : path.join(venvPath, 'bin', 'python');        // Caminho no Linux (Servidor/Coolify)

  // 3. Monta o comando utilizando o executável isolado
  const comandoPython = `"${pythonExecutable}" "${scriptPython}" --crimes "${caminhoCrimes}" --populacao "${caminhoPop}" --saida "${caminhoSQL}"`;

  console.log('A iniciar Motor Python no ambiente virtual...');
  
  // O Node dispara o Python[cite: 7]
  exec(comandoPython, (error, stdout, stderr) => {
    if (error) {
      console.error(`Erro no Python: ${error.message}`);
      console.error(`Detalhes (stderr): ${stderr}`); // Ajuda a ver se faltou algum pacote
      return res.status(500).json({ error: 'Falha ao processar as planilhas no script Python.' });
    }

    console.log('Python finalizou a criação do SQL. A injetar no MySQL...');

    // Adicionadas aspas ao redor do caminhoSQL para evitar falhas se houver espaços no caminho
    const comandoMySQL = `mysql -h ${process.env.DB_HOST} -P ${process.env.DB_PORT} -u ${process.env.DB_USER} -p${process.env.DB_PASSWORD} ${process.env.DB_NAME} < "${caminhoSQL}"`;

    exec(comandoMySQL, (dbError) => {
      // Limpeza dos ficheiros temporários para não lotar o servidor[cite: 7]
      if (fs.existsSync(caminhoCrimes)) fs.unlinkSync(caminhoCrimes);
      if (fs.existsSync(caminhoPop)) fs.unlinkSync(caminhoPop);
      if (fs.existsSync(caminhoSQL)) fs.unlinkSync(caminhoSQL);

      if (dbError) {
        console.error(`Erro ao injetar SQL: ${dbError.message}`);
        return res.status(500).json({ error: 'Erro ao guardar no banco de dados MySQL.' });
      }

      // Devolve a resposta de sucesso para o Next.js[cite: 7]
      return res.json({ message: 'Dados importados e integrados com sucesso!' });
    });
  });
};

export default { processarETL };