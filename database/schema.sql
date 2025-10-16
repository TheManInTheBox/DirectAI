-- =====================================================
-- Music Platform Database Schema
-- Target: Azure SQL Database / PostgreSQL
-- Version: 1.0
-- =====================================================

-- Audio Files Table
CREATE TABLE AudioFiles (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    OriginalFileName NVARCHAR(255) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    SizeBytes BIGINT NOT NULL,
    DurationMs INT NOT NULL,
    Format NVARCHAR(10) NOT NULL,
    UploadedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    Status NVARCHAR(20) NOT NULL,
    UserId NVARCHAR(100) NULL,
    
    CONSTRAINT CK_AudioFiles_Status CHECK (Status IN ('Uploaded', 'Analyzing', 'Analyzed', 'Failed')),
    INDEX IX_AudioFiles_UploadedAt (UploadedAt),
    INDEX IX_AudioFiles_Status (Status),
    INDEX IX_AudioFiles_UserId (UserId)
);

-- JAMS Annotations Table (JSON storage)
CREATE TABLE JAMSAnnotations (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    JamsJson NVARCHAR(MAX) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_JAMSAnnotations_AudioFileId (AudioFileId)
);

-- Analysis Results Table
CREATE TABLE AnalysisResults (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    Bpm FLOAT NOT NULL,
    MusicalKey NVARCHAR(10) NOT NULL,
    Mode NVARCHAR(10) NOT NULL,
    Tuning FLOAT NOT NULL,
    AnalyzedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_AnalysisResults_AudioFileId (AudioFileId),
    INDEX IX_AnalysisResults_Bpm (Bpm),
    INDEX IX_AnalysisResults_MusicalKey (MusicalKey)
);

-- Sections Table (Song structure)
CREATE TABLE Sections (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AnalysisResultId UNIQUEIDENTIFIER NOT NULL,
    StartTime FLOAT NOT NULL,
    EndTime FLOAT NOT NULL,
    Label NVARCHAR(50) NOT NULL,
    Confidence FLOAT NOT NULL DEFAULT 1.0,
    
    FOREIGN KEY (AnalysisResultId) REFERENCES AnalysisResults(Id) ON DELETE CASCADE,
    INDEX IX_Sections_AnalysisResultId (AnalysisResultId)
);

-- Chord Annotations Table
CREATE TABLE ChordAnnotations (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AnalysisResultId UNIQUEIDENTIFIER NOT NULL,
    StartTime FLOAT NOT NULL,
    EndTime FLOAT NOT NULL,
    Chord NVARCHAR(20) NOT NULL,
    Confidence FLOAT NOT NULL DEFAULT 1.0,
    
    FOREIGN KEY (AnalysisResultId) REFERENCES AnalysisResults(Id) ON DELETE CASCADE,
    INDEX IX_ChordAnnotations_AnalysisResultId (AnalysisResultId)
);

-- Beat Annotations Table
CREATE TABLE BeatAnnotations (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AnalysisResultId UNIQUEIDENTIFIER NOT NULL,
    Time FLOAT NOT NULL,
    Position INT NOT NULL,
    IsDownbeat BIT NOT NULL DEFAULT 0,
    
    FOREIGN KEY (AnalysisResultId) REFERENCES AnalysisResults(Id) ON DELETE CASCADE,
    INDEX IX_BeatAnnotations_AnalysisResultId (AnalysisResultId)
);

-- Stems Table (Source separation results)
CREATE TABLE Stems (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    Type NVARCHAR(20) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    DurationSeconds FLOAT NOT NULL,
    SeparatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    SourceSeparationModel NVARCHAR(50) NOT NULL,
    
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    INDEX IX_Stems_AudioFileId (AudioFileId),
    INDEX IX_Stems_Type (Type)
);

-- Generation Requests Table
CREATE TABLE GenerationRequests (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    AudioFileId UNIQUEIDENTIFIER NOT NULL,
    TargetStems NVARCHAR(500) NOT NULL, -- JSON array
    Parameters NVARCHAR(MAX) NOT NULL, -- JSON parameters
    Status NVARCHAR(20) NOT NULL,
    RequestedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CompletedAt DATETIME2 NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    
    FOREIGN KEY (AudioFileId) REFERENCES AudioFiles(Id) ON DELETE CASCADE,
    CONSTRAINT CK_GenerationRequests_Status CHECK (Status IN ('Pending', 'Planning', 'Queued', 'Generating', 'PostProcessing', 'Completed', 'Failed')),
    INDEX IX_GenerationRequests_AudioFileId (AudioFileId),
    INDEX IX_GenerationRequests_Status (Status)
);

-- Generated Stems Table
CREATE TABLE GeneratedStems (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    GenerationRequestId UNIQUEIDENTIFIER NOT NULL,
    Type NVARCHAR(20) NOT NULL,
    BlobUri NVARCHAR(1000) NOT NULL,
    DurationSeconds FLOAT NOT NULL,
    Format NVARCHAR(10) NOT NULL,
    SampleRate INT NOT NULL DEFAULT 44100,
    BitDepth INT NOT NULL DEFAULT 16,
    Channels INT NOT NULL DEFAULT 2,
    GeneratedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    Metadata NVARCHAR(MAX) NOT NULL, -- JSON metadata
    
    FOREIGN KEY (GenerationRequestId) REFERENCES GenerationRequests(Id) ON DELETE CASCADE,
    INDEX IX_GeneratedStems_GenerationRequestId (GenerationRequestId),
    INDEX IX_GeneratedStems_Type (Type)
);

-- Jobs Table (Orchestration tracking)
CREATE TABLE Jobs (
    Id UNIQUEIDENTIFIER PRIMARY KEY DEFAULT NEWID(),
    Type NVARCHAR(50) NOT NULL,
    EntityId UNIQUEIDENTIFIER NOT NULL,
    OrchestrationInstanceId NVARCHAR(100) NOT NULL,
    Status NVARCHAR(20) NOT NULL,
    StartedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    CompletedAt DATETIME2 NULL,
    ErrorMessage NVARCHAR(MAX) NULL,
    Metadata NVARCHAR(MAX) NULL, -- JSON metadata
    
    CONSTRAINT CK_Jobs_Status CHECK (Status IN ('Pending', 'Running', 'Completed', 'Failed', 'Cancelled')),
    INDEX IX_Jobs_OrchestrationInstanceId (OrchestrationInstanceId),
    INDEX IX_Jobs_Status (Status),
    INDEX IX_Jobs_Type (Type)
);

-- Optional: Full-text search indexes for metadata queries
-- CREATE FULLTEXT INDEX ON AnalysisResults(MusicalKey);

-- Sample queries for common operations
/*
-- Find all analyzed songs in C major with BPM between 120-140
SELECT af.OriginalFileName, ar.Bpm, ar.MusicalKey
FROM AudioFiles af
JOIN AnalysisResults ar ON af.Id = ar.AudioFileId
WHERE ar.MusicalKey = 'C' AND ar.Mode = 'major'
  AND ar.Bpm BETWEEN 120 AND 140;

-- Get all sections for a specific song
SELECT s.Label, s.StartTime, s.EndTime
FROM Sections s
JOIN AnalysisResults ar ON s.AnalysisResultId = ar.Id
WHERE ar.AudioFileId = '...';

-- Find all generation requests that are currently processing
SELECT gr.*, af.OriginalFileName
FROM GenerationRequests gr
JOIN AudioFiles af ON gr.AudioFileId = af.Id
WHERE gr.Status IN ('Planning', 'Queued', 'Generating');
*/
