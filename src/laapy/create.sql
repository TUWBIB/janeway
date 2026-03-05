DROP TABLE IF EXISTS api_call;
DROP TABLE IF EXISTS api_call_h;

CREATE TABLE IF NOT EXISTS api_call
(
    id MEDIUMINT NOT NULL AUTO_INCREMENT,
    target VARCHAR(10) NOT NULL,
    label VARCHAR(30) NULL,
    op VARCHAR(10) NOT NULL,
    url VARCHAR(500) NOT NULL,
    body MEDIUMTEXT NULL, 
    ts_begin DATETIME(6) NULL, 
    ts_end DATETIME(6) NULL,     
    status_code VARCHAR(3) NULL,
    error_code VARCHAR(10) NULL,
    error_message VARCHAR(500) NULL,
    PRIMARY KEY (id)
);

CREATE TABLE IF NOT EXISTS api_call_h LIKE api_call;
ALTER TABLE api_call_h 
    MODIFY COLUMN id int(11) NOT NULL,
    DROP PRIMARY KEY,
    ADD action VARCHAR(8) DEFAULT 'insert' FIRST, 
    ADD revision INT(6) DEFAULT 0 NULL AFTER action,
    ADD dt_datetime DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP AFTER revision,
    ADD PRIMARY KEY (id,revision);

DROP TRIGGER IF EXISTS api_call__ai;
DROP TRIGGER IF EXISTS api_call__au;
DROP TRIGGER IF EXISTS api_call__bd;

CREATE TRIGGER api_call__ai AFTER INSERT ON api_call
    FOR EACH ROW
    INSERT INTO api_call_h
    SELECT 'insert', 1, NOW(), t.* 
    FROM api_call AS t WHERE t.id = NEW.id;

CREATE TRIGGER api_call__au AFTER UPDATE ON api_call
    FOR EACH ROW
    INSERT INTO api_call_h
    SELECT 'update', (SELECT MAX(th.revision)+1 FROM api_call_h th2 WHERE th.id=th2.id AND th.revision=th2.revision),NOW(), t.* 
    FROM api_call AS t,api_call_h AS th WHERE t.id = NEW.id and th.id=t.id;

CREATE TRIGGER api_call__bd BEFORE DELETE ON api_call
    FOR EACH ROW
    INSERT INTO api_call_h
    SELECT 'delete', (SELECT MAX(th.revision)+1 FROM api_call_h th2 WHERE th.id=th2.id AND th.revision=th2.revision),NOW(), t.* 
    FROM api_call AS t,api_call_h AS th WHERE t.id = OLD.id and th.id=t.id;
