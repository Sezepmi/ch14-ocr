# Despliegue público — ch14-ocr (Render)

## URL esperada tras deploy

```text
https://ch14-ocr.onrender.com
```

Health: `https://ch14-ocr.onrender.com/health` → `{"ok":true,...}`

## Opción A — Un clic (recomendada)

1. Repo: https://github.com/sezep/ch14-ocr  
2. Abre: https://render.com/deploy?repo=https://github.com/sezep/ch14-ocr  
3. Crea el **Web Service** (plan **Standard** recomendado por RAM/EasyOCR).  
4. Espera el primer build (puede tardar 15–25 min por modelos OCR).  
5. Cuando esté **Live**, en appPlus ejecuta:

   ```powershell
   cd C:\Users\sezep\Documents\appPlus
   .\scripts\configurar-vercel-ocr.ps1
   ```

6. Redeploy Vercel (actualizador o `vercel --prod`).  
7. Prueba: `https://ch14.es/ocr/health`

## Opción B — Dashboard manual

- New → Web Service → Docker → repo `sezep/ch14-ocr`  
- Health check path: `/health`  
- Puerto: el que inyecte Render (`PORT`); el Dockerfile ya lo respeta.

## Vinculación con CH14

| Capa | Variable / ruta |
|------|-----------------|
| Navegador | `VITE_OCR_SERVICE_URL=/ocr` |
| ch14.es | `/ocr/*` → proxy Vercel `api/ocr` |
| Vercel servidor | `OCR_UPSTREAM_URL=https://ch14-ocr.onrender.com` |
| Python | `/health`, `/procesar`, `/procesar/batch` |

**No** uses `https://ch14.es` ni Supabase como `OCR_UPSTREAM_URL`.
