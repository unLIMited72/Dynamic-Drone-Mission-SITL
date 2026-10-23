"""Bounded diagnostic logs. No pixels stored here."""
import logging
from logging.handlers import RotatingFileHandler
class RotatingLog:
    def __init__(self,path):
        self.handler=RotatingFileHandler(path,maxBytes=8*1024*1024,backupCount=3)
        self.handler.setFormatter(logging.Formatter('%(message)s'))
    def write(self,text):
        self.handler.emit(logging.LogRecord('runtime',logging.INFO,'',0,text.rstrip('\n'),(),None))
    def flush(self): self.handler.flush()
    def close(self): self.handler.close()
    def __enter__(self): return self
    def __exit__(self,*_): self.close()
