"""Evidence-coverage capability — which evidence sets have a validator.

Pure logic over already-fetched Paramify data (the ``app`` layer does the I/O).
The Paramify API exposes no readable evidence↔validator link, so "associated"
means a validator has run against one of the evidence set's artifacts
(``artifacts[].validators[]``). The typed contract lives in ``models.py``; the
bucketing/orphan logic in ``coverage.py``.
"""
