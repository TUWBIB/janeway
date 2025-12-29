mysql -u $1 -p$2 $3 -e "UPDATE journal_journal SET domain='oes.zzz' WHERE code='OES';
UPDATE journal_journal SET domain='jfm.zzz' WHERE code='JFM';
UPDATE journal_journal SET domain='arw.zzz' WHERE code='ARW';
UPDATE journal_journal SET domain='iotw.zzz' WHERE code='IOTW';
UPDATE journal_journal SET domain='ef.zzz' WHERE code='EF';
UPDATE core_contacts SET email='it@ub.tuwien.ac.at';"
