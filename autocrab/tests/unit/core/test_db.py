from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from autocrab.core.db.models import Base, User, Channel, AgentSession

# Use in-memory SQLite for testing to avoid disk pollution
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base.metadata.create_all(bind=engine)

def test_database_model_relations():
    db = SessionLocal()
    
    # Create User
    user = User(username="test_user", email="test@autocrab.ai")
    db.add(user)
    db.commit()
    assert user.id is not None
    
    # Create Channel
    channel = Channel(name="CLI Test", platform="cli")
    db.add(channel)
    db.commit()
    assert channel.id is not None
    
    # Create Session linked to User and Channel
    session = AgentSession(user_id=user.id, channel_id=channel.id, agent_name="test_agent")
    db.add(session)
    db.commit()
    assert session.id is not None
    
    # Query back and verify relations
    saved_session = db.query(AgentSession).filter_by(id=session.id).first()
    assert saved_session.agent_name == "test_agent"
    assert saved_session.user.username == "test_user"
    assert saved_session.user.email == "test@autocrab.ai"
    assert saved_session.channel.platform == "cli"

    db.close()
