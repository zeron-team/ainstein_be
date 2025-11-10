from enum import Enum

class PatientEstado(str, Enum):
    internacion = "internacion"
    falta_epc = "falta_epc"
    epc_generada = "epc_generada"
    alta = "alta"

class EPCEstado(str, Enum):
    borrador = "borrador"
    validada = "validada"
    impresa = "impresa"
