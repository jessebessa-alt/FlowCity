import { exec } from 'child_process';
import path from 'path';
import fs from 'fs';
import { fileURLToPath } from 'url';

// Recria o __dirname que não existe por padrão em ES Modules (import)
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const processarETL = (req, res) => {
  // 1. Verifica se os ficheiros chegaram
  if (!req.files || !req.files.crimes || !req.files.populacao) {
    return res.status(400).json({ error: 'Os dois ficheiros são obrigatórios.' });
  }

  // Pega os caminhos temporários onde o Multer guardou os ficheiros
  const caminhoCrimes = req.files.crimes[0].path;
  const caminhoPop = req.files.populacao[0].path;
  const caminhoSQL = path.join(__dirname, '../../uploads/saida_motor.sql');

  // Onde o seu script Python está guardado no backend
  const scriptPython = path.join(__dirname, '../../scripts/gerar_banco_app.py');

  // 2. Monta o comando de terminal que o Node vai executar invisivelmente
  // Alterado para 'python' como alternativa caso 'python3' falhe no ambiente local do Windows
  const comandoPython = `python ${scriptPython} --crimes ${caminhoCrimes} --populacao ${caminhoPop} --saida ${caminhoSQL}`;

  console.log('A iniciar Motor Python...');
  
  // 3. O Node dispara o Python
  exec(comandoPython, (error, stdout, stderr) => {
    if (error) {
      console.error(`Erro no Python: ${error.message}`);
      return res.status(500).json({ error: 'Falha ao processar as planilhas no script Python.' });
    }

    console.log('Python finalizou a criação do SQL. A injetar no MySQL...');

    const comandoMySQL = `mysql -h ${process.env.DB_HOST} -P ${process.env.DB_PORT} -u ${process.env.DB_USER} -p${process.env.DB_PASSWORD} ${process.env.DB_NAME} < ${caminhoSQL}`;

    exec(comandoMySQL, (dbError) => {
      // Limpeza dos ficheiros temporários para não lotar o servidor
      if (fs.existsSync(caminhoCrimes)) fs.unlinkSync(caminhoCrimes);
      if (fs.existsSync(caminhoPop)) fs.unlinkSync(caminhoPop);
      if (fs.existsSync(caminhoSQL)) fs.unlinkSync(caminhoSQL);

      if (dbError) {
        console.error(`Erro ao injetar SQL: ${dbError.message}`);
        return res.status(500).json({ error: 'Erro ao guardar no banco de dados MySQL.' });
      }

      // Devolve a resposta de sucesso para o Next.js
      return res.json({ message: 'Dados importados e integrados com sucesso!' });
    });
  });
};

export default { processarETL };
