using System;
using Microsoft.EntityFrameworkCore.Migrations;

#nullable disable

namespace MusicPlatform.Api.Migrations
{
    /// <inheritdoc />
    public partial class AddAlbumArtworkUri : Migration
    {
        /// <inheritdoc />
        protected override void Up(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.AddColumn<Guid>(
                name: "AudioFileId1",
                table: "Stems",
                type: "uuid",
                nullable: true);

            migrationBuilder.CreateIndex(
                name: "IX_Stems_AudioFileId1",
                table: "Stems",
                column: "AudioFileId1");

            migrationBuilder.AddForeignKey(
                name: "FK_Stems_AudioFiles_AudioFileId1",
                table: "Stems",
                column: "AudioFileId1",
                principalTable: "AudioFiles",
                principalColumn: "Id");
        }

        /// <inheritdoc />
        protected override void Down(MigrationBuilder migrationBuilder)
        {
            migrationBuilder.DropForeignKey(
                name: "FK_Stems_AudioFiles_AudioFileId1",
                table: "Stems");

            migrationBuilder.DropIndex(
                name: "IX_Stems_AudioFileId1",
                table: "Stems");

            migrationBuilder.DropColumn(
                name: "AudioFileId1",
                table: "Stems");
        }
    }
}
