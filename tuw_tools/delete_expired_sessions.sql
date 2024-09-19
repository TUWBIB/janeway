DELETE FROM django_session WHERE expire_date < (SELECT DATE_SUB(curdate(), INTERVAL 1 MONTH));
