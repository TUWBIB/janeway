CREATE TABLE `django_session` (
	`session_key` VARCHAR(40) NOT NULL COLLATE 'utf8mb4_general_ci',
	`session_data` LONGTEXT NOT NULL COLLATE 'utf8mb4_general_ci',
	`expire_date` DATETIME(6) NOT NULL,
	PRIMARY KEY (`session_key`) USING BTREE,
	INDEX `django_session_expire_date_a5c62663` (`expire_date`) USING BTREE
)
COLLATE='utf8mb4_general_ci'
ENGINE=InnoDB
;
