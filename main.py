
from psycopg2.pool import SimpleConnectionPool
import os
from fastapi import FastAPI, Depends, HTTPException, status, UploadFile, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from passlib.context import CryptContext
import psycopg2
from pydantic import BaseModel, Field
from jose import jwt
from dotenv import load_dotenv
import redis
import json
from llama_index.core import SimpleDirectoryReader,VectorStoreIndex
from llama_index.embeddings.huggingface import HuggingFaceEmbedding
from llama_index.core import load_index_from_storage, StorageContext
from llama_index.llms.groq import Groq
from slowapi import Limiter
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi import _rate_limit_exceeded_handler

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "your-secret-key")
ALGORITHM = os.getenv("ALGORITHM", "HS256")

# Initialize Redis client
redis_client = redis.StrictRedis(host="localhost", port=6379, db=0)

try:
    redis_client = redis.Redis(
        host="localhost",
        port=6379,
        db=0,
        decode_responses=True,
        socket_timeout=2  # Prevents API from hanging if Redis is unresponsive
    )
except Exception as e:
   print(f"Failed to initialize Redis client: {e}")
   redis_client = None





# This switches Swagger to show a single "Token Input" box instead of a login form
security_scheme = HTTPBearer()

api_key = os.getenv("GROQ_API_KEY")
Large=Groq(model="llama3-70b-8192", temperature=0.7, max_tokens=500,api_key=api_key)

class sign(BaseModel):
    email: str = Field(description="User's email address")
    password: str = Field(
        min_length=8, description="Password must be at least 8 characters long")
    role: str = Field( description="User role, default is 'manager'")

class log(BaseModel):
    email: str = Field(description="User's email address")
    password: str = Field(
        min_length=8, description="Password must be at least 8 characters long")
    



app = FastAPI(title="Hashing API")
limiter = Limiter(key_func=get_remote_address)

app.state.limiter = limiter

app.add_exception_handler(
    RateLimitExceeded,
    _rate_limit_exceeded_handler
)

app.add_middleware(SlowAPIMiddleware)
hash = CryptContext(schemes=["bcrypt"], deprecated="auto")

# db = psycopg2.connect(
#     host="localhost",
#     database="Nitin",
#     user="postgres",
#     password="Nitin"
# )


db_pool = SimpleConnectionPool(
    minconn=1,
    maxconn=10,
    host="localhost",
    database="mydb",
    user="postgres",
    password="password",
    port=5432
)

# def get_db():
#     try:
#         conn = db
#         yield conn
#     finally:
#         pass



def get_db():
    conn = None

    try:
        conn = db_pool.getconn()
        yield conn

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:
        if conn:
            print("Returning connection to pool")
            db_pool.putconn(conn)


def create_token(user_id: str, role: str):
    try:
        payload = {"user_id": user_id, "role": role}
        token = jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)
        return token
    except Exception as e:
        return {"error": str(e)}



def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security_scheme)):
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        print(payload)
        return payload.get("user_id"), payload.get("role")
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid or expired token: {str(e)}"
        )

   
def verify_manager(user=Depends(verify_token)):
    print(f"Token payload: {user}")
    if user[1] == "manager":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Access denied: Managers only"
        )
    return user


@app.post("/signup")
async def sign_up(sign_data: sign, current_db=Depends(get_db)):
    try:
        hashed_password = hash.hash(sign_data.password)
        cursor = current_db.cursor()
        cursor.execute("INSERT INTO users (email, hashed_password,role) VALUES (%s, %s, %s)",
                       (sign_data.email, hashed_password, sign_data.role))
        current_db.commit()
        return {"message": "User signed up successfully"}
    except Exception as e:
        return {"error": str(e)}


@app.post("/login")
@limiter.limit("5/minute")
async def login(request: Request,log_data: log, current_db=Depends(get_db)):
    try:
        cursor = current_db.cursor()
        cursor.execute(
            "SELECT hashed_password,role FROM users WHERE email = %s", (log_data.email,))
        result = cursor.fetchone()
        print(result)

        if result and hash.verify(log_data.password, result[0]):
            user_role = result[1]
            token = create_token(user_id=log_data.email, role=user_role)
            return {
                "message": "Login successful",
                "token": token
            }
        else:
            return {"message": "Invalid email or password"}

    except Exception as e:
        return { "error": str(e)}




@app.get("/dashboard")
async def dashboard(
    current_db=Depends(get_db),
    token_user: str = Depends(verify_manager)
):
    cache_key = "dashboard:users_list"
    users = None

    # Try Redis
    if redis_client:
        try:
            cached_users = redis_client.get(cache_key)

            if cached_users:
                print("Cache Hit")
                users = json.loads(cached_users)

        except redis.RedisError as e:
            print(f"Redis read error: {e}")

    # Cache miss
    if users is None:
        try:
            print("Cache Miss")

            cursor = current_db.cursor()
            cursor.execute("SELECT email FROM users")

            users = [row[0] for row in cursor.fetchall()]

            cursor.close()

            # Store in Redis
            if redis_client:
                try:
                    redis_client.set(
                        cache_key,
                        json.dumps(users),
                    )
                    print("Data cached successfully")

                except redis.RedisError as e:
                    print(f"Redis write error: {e}")

        except Exception as e:
            print(f"Database error: {e}")

            raise HTTPException(
                status_code=500,
                detail="Database error"
            )

    return {
        "logged_in_as": token_user,
        "users": users
    }

path = "F:/seo_analysis/pdf_files"


@app.post("/file_up")
async def file_upload(file: UploadFile):
    print("running")
    if not file.filename.lower().endswith('.pdf'):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid file type. Only PDF files are allowed."
        )

    try:
        os.makedirs(path, exist_ok=True)
        print("work.........")

        file_path = os.path.join(path, file.filename)
        # os.makedirs(os.path.dirname(path), exist_ok=True)

        contents = await file.read()
        with open(file_path, "wb") as f:
            f.write(contents)

        return {
            "message": "PDF uploaded and saved successfully",
            "filename": file.filename,
            "content_type": file.content_type,
            "saved_path": file_path
        }

    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while saving the file: {str(e)}"
        )
   
@app.post("/create_embeddings")
def create_embeddings():
    PERSIST_DIR = "F:/seo_analysis/datastorage"
    
    try:
        documents = SimpleDirectoryReader(
            input_dir=path
            ).load_data()
        
        embedding_model = HuggingFaceEmbedding(model_name="sentence-transformers/all-MiniLM-L6-v2")
        
        if os.path.exists(PERSIST_DIR):
                storage_context = StorageContext.from_defaults(
                persist_dir=PERSIST_DIR)
                index = load_index_from_storage(storage_context)
                return {"message": "Index loaded from storage successfully"}
        else:
                 index = VectorStoreIndex.from_documents(documents, embed_model=embedding_model)
                 index.storage_context.persist(PERSIST_DIR)
                 return {"message": "Index created and saved to storage successfully"}
    except Exception as e:
        return {"error": str(e)}
    
    
@app.post("/query_embeddings")
def query_embeddings(query: str):
    PERSIST_DIR = "F:/seo_analysis/datastorage"
    
    try:
        if not os.path.exists(PERSIST_DIR):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Index not found. Please create embeddings first."
            )
        
        storage_context = StorageContext.from_defaults(persist_dir=PERSIST_DIR)
        index = load_index_from_storage(storage_context)
        
        resp = index.as_chat_engine(chat_mode="context", llm=Large)
        response=resp.chat(query)
        return {"response": response}
    
    except HTTPException as http_exc:
        raise http_exc  
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An error occurred while querying the index: {str(e)}"
        )

