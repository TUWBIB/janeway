mysql -u user -ppassword -e "SELECT concat('DROP TABLE IF EXISTS ', table_name, ';') FROM information_schema.tables WHERE table_schema ='janeway';" > drop_all_except_session.sql
sed -i '/django_session/d' drop_all_except_session.sql
sed -i '/concat/d' drop_all_except_session.sql
sed -i '1s/^/SET FOREIGN_KEY_CHECKS = 0;\n/' drop_all_except_session.sql
echo 'SET FOREIGN_KEY_CHECKS = 1;' >> drop_all_except_session.sql
