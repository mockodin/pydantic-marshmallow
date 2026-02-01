# Ecosystem Integration

pydantic-marshmallow works seamlessly with the Marshmallow ecosystem.

## Flask-Marshmallow

```python
from flask import Flask, request
from flask_marshmallow import Marshmallow
from pydantic_marshmallow import schema_for

app = Flask(__name__)
ma = Marshmallow(app)

class User(BaseModel):
    name: str
    email: EmailStr

UserSchema = schema_for(User)

@app.route("/users", methods=["POST"])
def create_user():
    schema = UserSchema()
    user = schema.load(request.json)
    # user is a Pydantic User instance
    return schema.dump(user)
```

## webargs

```python
from webargs.flaskparser import use_args
from pydantic_marshmallow import schema_for

UserSchema = schema_for(User)

@app.route("/users", methods=["POST"])
@use_args(UserSchema(), location="json")
def create_user(user):
    # user is a Pydantic User instance
    return {"message": f"Created {user.name}"}
```

## apispec

```python
from apispec import APISpec
from apispec.ext.marshmallow import MarshmallowPlugin
from pydantic_marshmallow import schema_for

spec = APISpec(
    title="My API",
    version="1.0.0",
    openapi_version="3.0.0",
    plugins=[MarshmallowPlugin()],
)

UserSchema = schema_for(User)
spec.components.schema("User", schema=UserSchema)

# Get OpenAPI spec
print(spec.to_dict())
```

## flask-smorest

```python
from flask_smorest import Api, Blueprint
from pydantic_marshmallow import schema_for

api = Api(app)
blp = Blueprint("users", __name__, url_prefix="/users")

UserSchema = schema_for(User)

@blp.route("/")
class Users(MethodView):
    @blp.arguments(UserSchema)
    @blp.response(201, UserSchema)
    def post(self, user):
        return user
```

## flask-rebar

```python
from flask_rebar import Rebar
from pydantic_marshmallow import schema_for

rebar = Rebar()
registry = rebar.create_handler_registry()

UserSchema = schema_for(User)

@registry.handles(
    rule="/users",
    method="POST",
    request_body_schema=UserSchema(),
    response_body_schema=UserSchema(),
)
def create_user():
    user = rebar.validated_body
    return user
```

## marshmallow-sqlalchemy

```python
from flask_sqlalchemy import SQLAlchemy
from pydantic_marshmallow import schema_for

db = SQLAlchemy(app)

class UserModel(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100))
    email = db.Column(db.String(100))

class User(BaseModel):
    id: int | None = None
    name: str
    email: str

# Use Pydantic schema for validation
UserSchema = schema_for(User)

@app.route("/users", methods=["POST"])
def create_user():
    schema = UserSchema()
    user_data = schema.load(request.json)
    
    # Create SQLAlchemy model from validated Pydantic data
    user = UserModel(**user_data.model_dump())
    db.session.add(user)
    db.session.commit()
    
    return schema.dump(user_data)
```

## marshmallow-oneofschema

For polymorphic schemas:

```python
from marshmallow_oneofschema import OneOfSchema
from pydantic_marshmallow import schema_for

class Dog(BaseModel):
    type: str = "dog"
    name: str
    breed: str

class Cat(BaseModel):
    type: str = "cat"
    name: str
    indoor: bool = True

class AnimalSchema(OneOfSchema):
    type_schemas = {
        "dog": schema_for(Dog),
        "cat": schema_for(Cat),
    }

    def get_obj_type(self, obj):
        return obj.type
```

## connexion (OpenAPI)

```python
from pydantic_marshmallow import pydantic_schema

@pydantic_schema
class User(BaseModel):
    name: str
    email: str

# Use in OpenAPI spec
# The .Schema attribute works with connexion's schema resolution
```
