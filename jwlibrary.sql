INSERT INTO "Note" ("NoteId", "Guid", "UserMarkId", "LocationId", "Title", "Content", "LastModified", "BlockType", "BlockIdentifier") 
VALUES ('4', 'aaabbbcc-dddd-eeee-ffff-ggghhhiiijjj', '6', '6', 'HOLA', 'Hola', '2023-04-16T19:08:08+00:00', '1', '5');

--INSERT INTO Location (LocationId, DocumentId, IssueTagNumber, KeySymbol, MepsLanguage, Type, Title) -- NO HACE FALTA
--VALUES (8, 2023281, 20230200, "w", 1, 0, "Saquémosle el jugo a la lectura de la Biblia");

INSERT INTO "main"."UserMark" ("UserMarkId", "ColorIndex", "LocationId", "StyleIndex", "UserMarkGuid", "Version") 
VALUES ('6', '3', '6', '0', 'aaabbbcc-dddd-eeee-ffff-ggghhhiiijjj', '1');

INSERT INTO "BlockRange" ("BlockRangeId", "BlockType", "Identifier", "StartToken", "EndToken", "UserMarkId")
VALUES ('6', '1', '5', '0', '1', '6');