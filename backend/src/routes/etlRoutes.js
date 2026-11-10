import express from 'express';
import multer from 'multer';
import path from 'path';
import { fileURLToPath } from 'url';
import etlController from '../controllers/etlController.js'; // Adicionado .js no final

const router = express.Router();

// Configuração para recriar o __dirname que não existe por padrão em ES Modules
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const upload = multer({ dest: path.join(__dirname, '../../uploads/') });

router.post('/upload', upload.fields([
  { name: 'crimes', maxCount: 1 },
  { name: 'populacao', maxCount: 1 }
]), etlController.processarETL);

export default router;
