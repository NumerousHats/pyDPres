from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, ForeignKey, DateTime
from sqlalchemy.orm import relationship


Base = declarative_base()


class PremisAgent(Base):
    __tablename__ = 'premis_agent'

    agent_id = Column(Integer, nullable=False, primary_key=True)
    agentIdentifierType = Column(String, nullable=False)
    agentIdentifierValue = Column(String, nullable=False)
    agentName = Column(String, nullable=False)
    agentType = Column(String, nullable=False)
    agentVersion = Column(String, nullable=False)


class PremisEvent(Base):
    __tablename__ = 'premis_event'

    event_id = Column(Integer, nullable=False, primary_key=True)
    eventIdentifierType = Column(String, nullable=False)
    eventIdentifierValue = Column(String, nullable=False)
    eventType = Column(String, nullable=False)
    eventDateTime = Column(DateTime, nullable=False)
    eventDetail = Column(String)
    eventOutcome = Column(String)
    object_id = Column(Integer, ForeignKey("premis_object.object_id"))
    agent_id = Column(Integer, ForeignKey("premis_agent.agent_id"))

    premis_object = relationship("PremisObject", back_populates="events")


class PremisObject(Base):
    __tablename__ = 'premis_object'

    object_id = Column(Integer, primary_key=True)
    objectIdentifierType = Column(String, nullable=False)
    objectIdentifierValue = Column(String, nullable=False)
    objectCategory = Column(String, nullable=False)
    messageDigestAlgorithm = Column(String, nullable=False)
    messageDigest = Column(String, nullable=False)
    file_size = Column(String)
    formatName = Column(String)
    formatRegistryName = Column(String)
    formatRegistryKey = Column(String)
    originalName = Column(String)
    contentLocationType = Column(String)
    contentLocationValue = Column(String, unique=True)
    relationshipType = Column(String)
    relationshipSubType = Column(String)
    relatedObject_id = Column(Integer, ForeignKey("premis_object.object_id"))
    ingest_id = Column(Integer, ForeignKey("pyDPres_ingest.ingest_id"))

    events = relationship("PremisEvent", back_populates="premis_object")
    properties = relationship('PremisSignificantProperties', back_populates="premis_object")
    ingest = relationship("PyDPresIngest", back_populates="premis_objects")
    related_objects = relationship("PremisObject")


class PremisSignificantProperties(Base):
    __tablename__ = "premis_significant_properties"

    significant_properties_id = Column(Integer, nullable=False, primary_key=True)
    object_id = Column(Integer, ForeignKey("premis_object.object_id"), nullable=False)
    significantPropertiesType = Column(String, nullable=False)
    significantPropertiesValue = Column(String, nullable=False)

    premis_object = relationship("PremisObject", back_populates="properties")


class PyDPresIngest(Base):
    __tablename__ = "pyDPres_ingest"

    ingest_id = Column(Integer, nullable=False, primary_key=True)
    ingest_start_time = Column(DateTime, nullable=False)
    ingest_end_time = Column(DateTime)
    ingest_note = Column(String)

    premis_objects = relationship("PremisObject", back_populates="ingest")


class PyDPresInfo(Base):
    __tablename__ = "pyDPres_info"

    info_id = Column(Integer, nullable=False, primary_key=True)
    info_name = Column(String, nullable=False)
    info_value = Column(String, nullable=False)
