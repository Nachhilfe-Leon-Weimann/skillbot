import discord


def is_teacher_predicate(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name == "Lehrer" for role in interaction.user.roles)


def is_student_predicate(interaction: discord.Interaction) -> bool:
    if not interaction.guild:
        return False
    if not isinstance(interaction.user, discord.Member):
        return False

    return any(role.name == "Schüler" for role in interaction.user.roles)
