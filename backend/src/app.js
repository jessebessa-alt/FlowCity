
import cors from "cors";
import express from "express";
import helmet from "helmet";

import { errorHandler } from "./middlewares/errorHandler.js";

import healthRoutes from "./routes/healthRoutes.js";
import authRoutes from "./routes/authRoutes.js";

import etlRoutes from "./routes/etlRoutes.js";

const app = express();

app.use(helmet());

app.use(
    cors({
        origin: [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3001" // Adicionado caso o NextJS suba na 3001 por estar ocupado
        ]
    })
);

app.use(express.json());

app.get("/", (request, response) => {
    response.json({
        message: "API do AlertABC funcionando!"
    });
});

app.use("/api/health", healthRoutes);
app.use("/api/auth", authRoutes);
app.use("/api/etl", etlRoutes); 

app.use(errorHandler);

export default app;
