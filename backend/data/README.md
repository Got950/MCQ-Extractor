# Data directory

PDF uploads are stored under `../uploads` (or S3 when configured).

Application data (users, jobs, questions) lives in **MongoDB Atlas**. Configure
`MONGODB_URI` in `.env` and run:

```bash
python -m scripts.init_database
```
