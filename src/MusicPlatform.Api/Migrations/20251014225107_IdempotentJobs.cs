using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class IdempotentJobs : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<string>(
                name: "Checkpoints",
                table: "Jobs",
                type: "text",
                nullable: false,
                defaultValue: "");

            migrationBuilder.AddColumn<string>(
                name: "CurrentStep",
                table: "Jobs",
                type: "character varying(100)",
                maxLength: 100,
                nullable: true);

            migrationBuilder.AddColumn<string>(
                name: "IdempotencyKey",
                table: "Jobs",
                type: "character varying(64)",
                maxLength: 64,
                nullable: true);

            migrationBuilder.AddColumn<DateTime>(
                name: "LastHeartbeat",
                table: "Jobs",
                type: "timestamp with time zone",
                nullable: true);

            migrationBuilder.AddColumn<int>(
                name: "MaxRetries",
                table: "Jobs",
                type: "integer",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<int>(
                name: "RetryCount",
                table: "Jobs",
                type: "integer",
                nullable: false,
                defaultValue: 0);

            migrationBuilder.AddColumn<string>(
                name: "WorkerInstanceId",
                table: "Jobs",
                type: "character varying(200)",
                maxLength: 200,
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_IdempotencyKey",
                table: "Jobs",
                column: "IdempotencyKey",
                unique: true);

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_LastHeartbeat",
                table: "Jobs",
                column: "LastHeartbeat");

            migrationBuilder.CreateIndex(
                name: "IX_Jobs_WorkerInstanceId",
                table: "Jobs",
                column: "WorkerInstanceId");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropIndex(
                name: "IX_Jobs_IdempotencyKey",
                table: "Jobs");

            migrationBuilder.DropIndex(
                name: "IX_Jobs_LastHeartbeat",
                table: "Jobs");

            migrationBuilder.DropIndex(
                name: "IX_Jobs_WorkerInstanceId",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "Checkpoints",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "CurrentStep",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "IdempotencyKey",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "LastHeartbeat",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "MaxRetries",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "RetryCount",
                table: "Jobs");

            migrationBuilder.DropColumn(
                name: "WorkerInstanceId",
                table: "Jobs");
        }
    }
}
