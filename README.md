
## 🚀 Features

* **Database Engine:** Reliable, atomic operations backed by **PostgreSQL** alongside modern async ORM connections.
* **Authentication & Authorization:** Secure user authentication using **JWT (JSON Web Tokens)** with access and refresh token flows.
* **Password Security:** Secure password hashing using **Argon2** / **Bcrypt** via `passlib`.
* **Rate Limiting:** IP and user-based rate limiting powered by **Redis** to protect against Brute Force and DDoS attacks.
* **Caching Layer:** High-speed data caching with **Redis** to minimize PostgreSQL database read load and optimize response times.
* **Asynchronous Architecture:** Fully async database operations and background tasks utilizing FastAPI's native capabilities.

---

## 🛠️ Tech Stack

* **Framework:** [FastAPI](https://fastapi.tiangolo.com/)
* **ASGI Server:** [Uvicorn](https://www.uvicorn.org/)
* **Database:** [PostgreSQL](https://www.postgresql.org/)
* **In-Memory Cache (Rate Limit):** [Redis](https://redis.io/)
* **Database ORM:** [SQLAlchemy (Async Engine)](https://www.sqlalchemy.org/) / [SQLModel](https://sqlmodel.tiangolo.com/)

---

## 📋 Prerequisites

Ensure you have the following installed on your local machine:
* Python 3.10+
* Redis Server (Running locally or hosted)
* PostgreSQL Database Server (Instance running locally or via Docker)

---

## 🔧 Getting Started
