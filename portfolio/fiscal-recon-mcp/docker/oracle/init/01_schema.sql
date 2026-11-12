-- Runs once on first container start, as the APP_USER schema owner.
ALTER SESSION SET CURRENT_SCHEMA = RECON;

CREATE TABLE legacy_fiscal_documents (
    origin_branch      VARCHAR2(10)  NOT NULL,
    destination_branch VARCHAR2(10)  NOT NULL,
    document_number    VARCHAR2(20)  NOT NULL,
    series             VARCHAR2(5)   NOT NULL,
    issue_date         DATE          NOT NULL,
    net_value          NUMBER(15, 2) NOT NULL,
    tax_value          NUMBER(15, 2) NOT NULL,
    CONSTRAINT pk_legacy_docs PRIMARY KEY (origin_branch, destination_branch, document_number, series)
);

CREATE INDEX idx_legacy_docs_date ON legacy_fiscal_documents (issue_date);
