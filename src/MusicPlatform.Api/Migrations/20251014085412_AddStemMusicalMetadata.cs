using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddStemMusicalMetadata : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "AnalysisErrorMessage",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "AnalysisStatus",
                table: "Stems",
                type: "integer",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<DateTime>(
                name: "AnalyzedAt",
                table: "Stems",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Beats",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "Bpm",
                table: "Stems",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "ChordProgression",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<long>(
                name: "FileSizeBytes",
                table: "Stems",
                type: "bigint",
                nullable: false,
                defaultValue: 0L);

            migrationBuilder.AddColumn<string>(
                name: "JamsUri",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Key",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "PeakLevel",
                table: "Stems",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "RmsLevel",
                table: "Stems",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "Sections",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "SpectralCentroid",
                table: "Stems",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "TimeSignature",
                table: "Stems",
                type: "text",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "TuningFrequency",
                table: "Stems",
                type: "double precision",
                nullable: true);

            migrationBuilder.AddColumn<double>(
                name: "ZeroCrossingRate",
                table: "Stems",
                type: "double precision",
                nullable: true);
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropColumn(
                name: "AnalysisErrorMessage",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "AnalysisStatus",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "AnalyzedAt",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "Beats",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "Bpm",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "ChordProgression",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "FileSizeBytes",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "JamsUri",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "Key",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "PeakLevel",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "RmsLevel",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "Sections",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "SpectralCentroid",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "TimeSignature",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "TuningFrequency",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "ZeroCrossingRate",
                table: "Stems");
        }
    }
}
