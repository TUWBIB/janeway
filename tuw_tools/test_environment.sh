mysql -u $1 -p$2 $3 -e "UPDATE journal_journal SET domain='test.oes.tuwien.ac.at' WHERE code='OES';
UPDATE journal_journal SET domain='test.journal.ifm.tuwien.ac.at' WHERE code='JFM';
UPDATE journal_journal SET domain='test-arw-proceedings.acin.tuwien.ac.at' WHERE code='ARW';
UPDATE journal_journal SET domain='test-iotw-proceedings.dsg.tuwien.ac.at' WHERE code='IOTW';
UPDATE journal_journal SET domain='test-euroforth.complang.tuwien.ac.at' WHERE code='EF';
UPDATE core_contacts SET email='openjournals@tuwien.ac.at';"